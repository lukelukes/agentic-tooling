import { priceOrder, PricingError, type CouponTerms, type Quote } from './pricing.js';
import type { Clock, IdSource, OrderMailer } from './ports.js';
import type { CheckoutStore, StoredOrder } from './store.js';

export interface PlaceOrderRequest {
  customerId: string;
  email: string;
  items: Array<{ sku: string; quantity: number }>;
  couponCode?: string;
}

export type RejectionReason =
  | 'EMPTY_CART'
  | 'INVALID_QUANTITY'
  | 'UNKNOWN_SKU'
  | 'OUT_OF_STOCK'
  | 'UNKNOWN_COUPON'
  | 'COUPON_EXPIRED'
  | 'COUPON_ALREADY_USED'
  | 'COUPON_EXHAUSTED';

export type PlaceOrderResult =
  | { ok: true; order: StoredOrder; quote: Quote; emailSent: boolean }
  | { ok: false; reason: RejectionReason; detail?: string };

class Rejected extends Error {
  constructor(
    readonly reason: RejectionReason,
    readonly detail?: string,
  ) {
    super(reason);
  }
}

export interface CheckoutDeps {
  store: CheckoutStore;
  mailer: OrderMailer;
  clock: Clock;
  ids: IdSource;
}

/**
 * Feature entry point: validate the cart, price it, reserve stock, redeem the
 * coupon and persist the order atomically, then email a confirmation.
 * A failed email never undoes a committed order.
 */
export class CheckoutService {
  constructor(private readonly deps: CheckoutDeps) {}

  async placeOrder(req: PlaceOrderRequest): Promise<PlaceOrderResult> {
    const { store, mailer, clock, ids } = this.deps;
    if (req.items.length === 0) return { ok: false, reason: 'EMPTY_CART' };

    let committed: { order: StoredOrder; quote: Quote };
    try {
      committed = store.inTransaction(() => {
        const lines = req.items.map((item) => {
          const product = store.getProduct(item.sku);
          if (!product) throw new Rejected('UNKNOWN_SKU', item.sku);
          return { sku: item.sku, unitPriceCents: product.priceCents, quantity: item.quantity };
        });

        const now = clock.now();
        let coupon: CouponTerms | null = null;
        if (req.couponCode !== undefined) {
          const found = store.findCoupon(req.couponCode);
          if (!found) throw new Rejected('UNKNOWN_COUPON', req.couponCode);
          if (now.getTime() > Date.parse(found.validUntil)) throw new Rejected('COUPON_EXPIRED', found.code);
          if (store.hasRedeemed(found.code, req.customerId)) throw new Rejected('COUPON_ALREADY_USED', found.code);
          if (store.redemptionCount(found.code) >= found.maxRedemptions) {
            throw new Rejected('COUPON_EXHAUSTED', found.code);
          }
          coupon = found;
        }

        let quote: Quote;
        try {
          quote = priceOrder(lines, coupon);
        } catch (err) {
          if (err instanceof PricingError) throw new Rejected('INVALID_QUANTITY', err.message);
          throw err;
        }

        for (const line of lines) {
          if (!store.reserveStock(line.sku, line.quantity)) throw new Rejected('OUT_OF_STOCK', line.sku);
        }
        // Only consume the coupon when it actually discounted the order.
        if (coupon && quote.couponApplied) store.recordRedemption(coupon.code, req.customerId);

        const order: StoredOrder = {
          id: `ord_${ids.next()}`,
          customerId: req.customerId,
          email: req.email,
          totalCents: quote.totalCents,
          couponCode: quote.couponApplied && coupon ? coupon.code : null,
          createdAt: now.toISOString(),
        };
        store.insertOrder(order);
        return { order, quote };
      });
    } catch (err) {
      if (err instanceof Rejected) return { ok: false, reason: err.reason, detail: err.detail };
      throw err;
    }

    let emailSent = true;
    try {
      await mailer.sendOrderConfirmation({
        to: committed.order.email,
        orderId: committed.order.id,
        totalCents: committed.order.totalCents,
        lines: req.items.map(({ sku, quantity }) => ({ sku, quantity })),
      });
    } catch {
      emailSent = false;
    }
    return { ok: true, ...committed, emailSent };
  }
}
