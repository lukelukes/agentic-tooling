// Pure pricing rules for a checkout. All amounts are integer cents.

export interface PriceLine {
  sku: string;
  unitPriceCents: number;
  quantity: number;
}

export interface CouponTerms {
  code: string;
  percentOff: number; // 1..100
  minSubtotalCents: number; // measured after volume discounts
}

export interface Quote {
  lines: Array<PriceLine & { grossCents: number; volumeDiscountCents: number }>;
  subtotalCents: number; // after volume discounts, before coupon
  couponDiscountCents: number;
  couponApplied: boolean; // true only when couponDiscountCents > 0
  shippingCents: number;
  totalCents: number;
}

export class PricingError extends Error {}

export const MAX_QUANTITY_PER_LINE = 999;
export const FREE_SHIPPING_THRESHOLD_CENTS = 5_000;
export const FLAT_SHIPPING_CENTS = 499;

// Checked from the largest tier down; the first tier whose minQuantity is met wins.
const VOLUME_TIERS = [
  { minQuantity: 50, percentOff: 10 },
  { minQuantity: 10, percentOff: 5 },
] as const;

export function volumeDiscountPercent(quantity: number): number {
  for (const tier of VOLUME_TIERS) {
    if (quantity >= tier.minQuantity) return tier.percentOff;
  }
  return 0;
}

export function priceOrder(lines: PriceLine[], coupon: CouponTerms | null): Quote {
  if (lines.length === 0) throw new PricingError('cannot price an empty order');

  const priced = lines.map((line) => {
    if (!Number.isInteger(line.quantity) || line.quantity < 1 || line.quantity > MAX_QUANTITY_PER_LINE) {
      throw new PricingError(`invalid quantity ${line.quantity} for ${line.sku}`);
    }
    const grossCents = line.unitPriceCents * line.quantity;
    // Per-line volume discount, rounded half up to the cent.
    const volumeDiscountCents = Math.round((grossCents * volumeDiscountPercent(line.quantity)) / 100);
    return { ...line, grossCents, volumeDiscountCents };
  });

  const subtotalCents = priced.reduce((sum, l) => sum + l.grossCents - l.volumeDiscountCents, 0);

  const couponEligible = coupon !== null && subtotalCents >= coupon.minSubtotalCents;
  // Coupon discount is rounded down so we never give away more than the advertised percentage.
  const couponDiscountCents = couponEligible ? Math.floor((subtotalCents * coupon.percentOff) / 100) : 0;
  // Applied (and so redeemed) only when it actually reduces the price; a discount that rounds to 0 is not applied.
  const couponApplied = couponDiscountCents > 0;

  const merchandiseCents = subtotalCents - couponDiscountCents;
  // Free shipping is judged on what the customer actually pays for merchandise.
  const shippingCents = merchandiseCents >= FREE_SHIPPING_THRESHOLD_CENTS ? 0 : FLAT_SHIPPING_CENTS;

  return {
    lines: priced,
    subtotalCents,
    couponDiscountCents,
    couponApplied,
    shippingCents,
    totalCents: merchandiseCents + shippingCents,
  };
}
