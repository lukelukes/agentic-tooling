import { randomUUID } from 'node:crypto';

export interface EventRecord {
  id: string;
  title: string;
  capacity: number;
  startsAt: string; // ISO-8601
  basePriceCents: number;
  earlyBirdDays: number; // registering at least this many days before start earns the early-bird rate
}

export type RegistrationStatus = 'CONFIRMED' | 'WAITLISTED' | 'CANCELLED';

export interface Registration {
  id: string;
  eventId: string;
  email: string;
  status: RegistrationStatus;
  priceCents: number;
  registeredAt: string;
}

/** Persistence for events and registrations. Owned by this service. */
export interface EventRepository {
  findEvent(id: string): Promise<EventRecord | undefined>;
  findRegistration(id: string): Promise<Registration | undefined>;
  listRegistrations(eventId: string): Promise<Registration[]>;
  save(registration: Registration): Promise<void>;
}

/** The repository the service runs on in production (single-node deployment). */
export class InMemoryEventRepository implements EventRepository {
  private readonly events = new Map<string, EventRecord>();
  private readonly registrations = new Map<string, Registration>();

  addEvent(event: EventRecord): void {
    this.events.set(event.id, { ...event });
  }
  async findEvent(id: string) {
    const e = this.events.get(id);
    return e && { ...e };
  }
  async findRegistration(id: string) {
    const r = this.registrations.get(id);
    return r && { ...r };
  }
  async listRegistrations(eventId: string) {
    return [...this.registrations.values()]
      .filter((r) => r.eventId === eventId)
      .sort((a, b) => a.registeredAt.localeCompare(b.registeredAt))
      .map((r) => ({ ...r }));
  }
  async save(registration: Registration) {
    this.registrations.set(registration.id, { ...registration });
  }
}

/** Outbound email through a third-party provider. */
export interface Notifier {
  send(to: string, subject: string, body: string): Promise<void>;
}

export class EventNotFoundError extends Error {}
export class RegistrationClosedError extends Error {}
export class DuplicateRegistrationError extends Error {}

const DAY_MS = 24 * 60 * 60 * 1000;
const EARLY_BIRD_PERCENT_OFF = 20;
const LAST_MINUTE_SURCHARGE_PERCENT = 10;

export class RegistrationService {
  constructor(
    private readonly repo: EventRepository,
    private readonly notifier: Notifier,
  ) {}

  async register(eventId: string, rawEmail: string): Promise<Registration> {
    const event = await this.repo.findEvent(eventId);
    if (!event) throw new EventNotFoundError(eventId);

    const now = new Date();
    if (now.getTime() >= Date.parse(event.startsAt)) throw new RegistrationClosedError(eventId);

    const email = this.normalizeEmail(rawEmail);
    const existing = await this.repo.listRegistrations(eventId);
    if (existing.some((r) => r.email === email && r.status !== 'CANCELLED')) {
      throw new DuplicateRegistrationError(email);
    }

    const confirmed = await this.countConfirmed(eventId);
    const status: RegistrationStatus = confirmed < event.capacity ? 'CONFIRMED' : 'WAITLISTED';
    const registration: Registration = {
      id: randomUUID(),
      eventId,
      email,
      status,
      priceCents: this.computePrice(event, now),
      registeredAt: now.toISOString(),
    };
    await this.repo.save(registration);

    await this.notifySafely(
      email,
      status === 'CONFIRMED' ? `You're in: ${event.title}` : `Waitlisted: ${event.title}`,
      status === 'CONFIRMED'
        ? `See you there. Amount due: ${formatCents(registration.priceCents)}.`
        : `The event is full. We'll email you if a seat opens up.`,
    );
    return registration;
  }

  /** Cancels a registration. A freed confirmed seat goes to the earliest waitlisted registration. */
  async cancel(registrationId: string): Promise<void> {
    const registration = await this.repo.findRegistration(registrationId);
    if (!registration || registration.status === 'CANCELLED') return;
    const wasConfirmed = registration.status === 'CONFIRMED';
    await this.repo.save({ ...registration, status: 'CANCELLED' });
    if (!wasConfirmed) return;

    const event = await this.repo.findEvent(registration.eventId);
    const next = (await this.repo.listRegistrations(registration.eventId)).find((r) => r.status === 'WAITLISTED');
    if (!event || !next) return;
    await this.repo.save({ ...next, status: 'CONFIRMED' });
    await this.notifySafely(
      next.email,
      `A seat opened up: ${event.title}`,
      `You're confirmed. Amount due: ${formatCents(next.priceCents)}.`,
    );
  }

  private normalizeEmail(email: string): string {
    return email.trim().toLowerCase();
  }

  private async countConfirmed(eventId: string): Promise<number> {
    const all = await this.repo.listRegistrations(eventId);
    return all.filter((r) => r.status === 'CONFIRMED').length;
  }

  private computePrice(event: EventRecord, now: Date): number {
    const msUntilStart = Date.parse(event.startsAt) - now.getTime();
    if (msUntilStart >= event.earlyBirdDays * DAY_MS) {
      return Math.round((event.basePriceCents * (100 - EARLY_BIRD_PERCENT_OFF)) / 100);
    }
    if (msUntilStart < DAY_MS) {
      return Math.round((event.basePriceCents * (100 + LAST_MINUTE_SURCHARGE_PERCENT)) / 100);
    }
    return event.basePriceCents;
  }

  private async notifySafely(to: string, subject: string, body: string): Promise<void> {
    try {
      await this.notifier.send(to, subject, body);
    } catch {
      // Email is best-effort; the registration already stands.
    }
  }
}

function formatCents(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}
