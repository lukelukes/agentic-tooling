import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  DuplicateRegistrationError,
  RegistrationService,
  type EventRecord,
  type EventRepository,
  type Notifier,
  type Registration,
} from '../src/registration.js';

const DAY = 24 * 60 * 60 * 1000;

function makeEvent(overrides: Partial<EventRecord> = {}): EventRecord {
  return {
    id: 'evt-1',
    title: 'TS Conf',
    capacity: 2,
    startsAt: new Date(Date.now() + 30 * DAY).toISOString(),
    basePriceCents: 10000,
    earlyBirdDays: 14,
    ...overrides,
  };
}

describe('RegistrationService', () => {
  let repo: {
    findEvent: ReturnType<typeof vi.fn>;
    findRegistration: ReturnType<typeof vi.fn>;
    listRegistrations: ReturnType<typeof vi.fn>;
    save: ReturnType<typeof vi.fn>;
  };
  let notifier: { send: ReturnType<typeof vi.fn> };
  let service: RegistrationService;

  beforeEach(() => {
    repo = {
      findEvent: vi.fn(),
      findRegistration: vi.fn(),
      listRegistrations: vi.fn(),
      save: vi.fn(),
    };
    notifier = { send: vi.fn().mockResolvedValue(undefined) };
    service = new RegistrationService(repo as unknown as EventRepository, notifier as unknown as Notifier);
  });

  it('test1', async () => {
    repo.findEvent.mockResolvedValue(makeEvent());
    repo.listRegistrations.mockResolvedValue([]);
    const r = await service.register('evt-1', 'Ann@Example.com');
    expect(r.status).toBe('CONFIRMED');
    expect(repo.findEvent).toHaveBeenCalledWith('evt-1');
    expect(repo.save).toHaveBeenCalledTimes(1);
  });

  it('calls repository correctly', async () => {
    repo.findEvent.mockResolvedValue(makeEvent());
    repo.listRegistrations.mockResolvedValue([]);
    const countSpy = vi.spyOn(service as any, 'countConfirmed');
    await service.register('evt-1', 'ann@example.com');
    expect(repo.findEvent).toHaveBeenCalledBefore(repo.listRegistrations);
    expect(repo.listRegistrations).toHaveBeenCalledTimes(2);
    expect(countSpy).toHaveBeenCalledWith('evt-1');
    expect(repo.save).toHaveBeenCalledWith(
      expect.objectContaining({ eventId: 'evt-1', email: 'ann@example.com', status: 'CONFIRMED' }),
    );
  });

  it('works', async () => {
    const event = makeEvent({ capacity: 2 });
    repo.findEvent.mockResolvedValue(event);
    const saved: Registration[] = [];
    repo.listRegistrations.mockImplementation(async () => saved);
    repo.save.mockImplementation(async (r: Registration) => {
      saved.push(r);
    });
    const emails = ['a@x.io', 'b@x.io', 'c@x.io', 'd@x.io'];
    for (let i = 0; i < emails.length; i++) {
      const r = await service.register('evt-1', emails[i]);
      if (i < event.capacity) {
        expect(r.status).toBe('CONFIRMED');
      } else {
        expect(r.status).toBe('WAITLISTED');
      }
    }
    expect(saved.length).toBe(4);
  });

  it('normalizes email', () => {
    expect((service as any).normalizeEmail('  Ann@Example.COM ')).toBe('ann@example.com');
  });

  it('normalizes email 2', () => {
    expect((service as any).normalizeEmail('bob@example.com')).toBe('bob@example.com');
  });

  it('handles edge case', async () => {
    repo.findEvent.mockResolvedValue(makeEvent());
    repo.listRegistrations.mockResolvedValue([
      {
        id: 'r1',
        eventId: 'evt-1',
        email: 'ann@example.com',
        status: 'CONFIRMED',
        priceCents: 8000,
        registeredAt: new Date().toISOString(),
      },
    ]);
    await expect(service.register('evt-1', 'ANN@example.com')).rejects.toBeInstanceOf(DuplicateRegistrationError);
    expect(repo.save).not.toHaveBeenCalled();
  });

  it('early bird price', () => {
    const event = makeEvent({ startsAt: new Date(Date.now() + 30 * DAY).toISOString() });
    expect((service as any).computePrice(event, new Date())).toBe(8000);
  });

  it('early bird price 2', () => {
    // exactly on the boundary; add a second of slack so it doesn't flake
    const event = makeEvent({ startsAt: new Date(Date.now() + 14 * DAY + 1000).toISOString() });
    expect((service as any).computePrice(event, new Date())).toBe(8000);
  });

  it('regular price', () => {
    const event = makeEvent({ startsAt: new Date(Date.now() + 5 * DAY).toISOString() });
    expect((service as any).computePrice(event, new Date())).toBe(10000);
  });

  it('late price', () => {
    const event = makeEvent({ startsAt: new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString() });
    expect((service as any).computePrice(event, new Date())).toBe(11000);
  });

  it('sets registeredAt', async () => {
    repo.findEvent.mockResolvedValue(makeEvent());
    repo.listRegistrations.mockResolvedValue([]);
    const before = new Date().toISOString();
    await new Promise((resolve) => setTimeout(resolve, 20));
    const r = await service.register('evt-1', 'ann@example.com');
    expect(r.registeredAt > before).toBe(true);
  });

  it('sends email', async () => {
    repo.findEvent.mockResolvedValue(makeEvent());
    repo.listRegistrations.mockResolvedValue([]);
    await service.register('evt-1', 'ann@example.com');
    expect(notifier.send).toHaveBeenCalledTimes(1);
    expect(notifier.send.mock.calls[0][0]).toBe('ann@example.com');
  });
});
