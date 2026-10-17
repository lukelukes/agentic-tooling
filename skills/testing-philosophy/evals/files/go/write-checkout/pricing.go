package checkout

// Volume discount tiers by quantity of a single SKU (after merging duplicate
// SKUs in one order):
//
//	1-9 units: 0%   10-49 units: 5%   50-99 units: 10%   100+ units: 15%
//
// A coupon applies only when the subtotal is at least MinSubtotalCents; its
// discount is capped at MaxCouponDiscountCents. Shipping is free when the
// subtotal after the coupon discount is at least FreeShippingCents.
// All percentages round half up to the nearest cent.
const (
	MaxCouponDiscountCents int64 = 5000
	FreeShippingCents      int64 = 7500
	ShippingCents          int64 = 499
)

type PricedLine struct {
	SKU       string
	Qty       int
	UnitCents int64
}

type Totals struct {
	SubtotalCents int64
	DiscountCents int64
	ShippingCents int64
	TotalCents    int64
}

func volumeDiscountPercent(qty int) int64 {
	switch {
	case qty >= 100:
		return 15
	case qty >= 50:
		return 10
	case qty >= 10:
		return 5
	default:
		return 0
	}
}

// percentOf returns amount*pct/100 rounded half up.
func percentOf(amount, pct int64) int64 {
	return (amount*pct + 50) / 100
}

// PriceOrder computes order totals. coupon may be nil.
func PriceOrder(lines []PricedLine, coupon *Coupon) Totals {
	var t Totals
	for _, l := range lines {
		gross := l.UnitCents * int64(l.Qty)
		t.SubtotalCents += gross - percentOf(gross, volumeDiscountPercent(l.Qty))
	}
	if coupon != nil && t.SubtotalCents >= coupon.MinSubtotalCents {
		t.DiscountCents = min(percentOf(t.SubtotalCents, int64(coupon.PercentOff)), MaxCouponDiscountCents)
	}
	if t.SubtotalCents-t.DiscountCents < FreeShippingCents {
		t.ShippingCents = ShippingCents
	}
	t.TotalCents = t.SubtotalCents - t.DiscountCents + t.ShippingCents
	return t
}
