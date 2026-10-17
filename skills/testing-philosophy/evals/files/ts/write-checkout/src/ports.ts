import { randomBytes } from 'node:crypto';

export interface Clock {
  now(): Date;
}

export const systemClock: Clock = { now: () => new Date() };

/** Source of randomness for order identifiers. */
export interface IdSource {
  next(): string;
}

export const cryptoIds: IdSource = {
  next: () => randomBytes(6).toString('hex'),
};

export interface OrderConfirmation {
  to: string;
  orderId: string;
  totalCents: number;
  lines: Array<{ sku: string; quantity: number }>;
}

/** Outbound transactional email. Owned by a third-party provider. */
export interface OrderMailer {
  sendOrderConfirmation(message: OrderConfirmation): Promise<void>;
}

/** Production mailer: POSTs to the email provider's HTTP API. */
export class HttpOrderMailer implements OrderMailer {
  constructor(
    private readonly endpoint: string,
    private readonly apiKey: string,
  ) {}

  async sendOrderConfirmation(message: OrderConfirmation): Promise<void> {
    const res = await fetch(this.endpoint, {
      method: 'POST',
      headers: { authorization: `Bearer ${this.apiKey}`, 'content-type': 'application/json' },
      body: JSON.stringify({ template: 'order-confirmation', ...message }),
    });
    if (!res.ok) throw new Error(`mail provider responded ${res.status}`);
  }
}
