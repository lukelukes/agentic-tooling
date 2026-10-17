package com.example.orders;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * In-process pricing rules.
 * Bulk discount: 10-49 units get 5% off, 50 or more get 10% off.
 * Promo code "WELCOME10" takes a further 10 EUR (1000 cents) off, never below zero.
 * Percentages are rounded half-even to the cent.
 */
public class PricingCalculator {

    public Quote quote(long unitPriceCents, int quantity, String promoCode) {
        long subtotal = unitPriceCents * quantity;
        long bulk = roundHalfEven(subtotal * bulkDiscountPercent(quantity), 100);
        long promo = "WELCOME10".equals(promoCode) ? Math.min(1000, subtotal - bulk) : 0;
        long discount = bulk + promo;
        return new Quote(subtotal, discount, subtotal - discount);
    }

    int bulkDiscountPercent(int quantity) {
        if (quantity >= 50) {
            return 10;
        }
        if (quantity >= 10) {
            return 5;
        }
        return 0;
    }

    private long roundHalfEven(long numerator, long denominator) {
        return BigDecimal.valueOf(numerator)
                .divide(BigDecimal.valueOf(denominator), 0, RoundingMode.HALF_EVEN)
                .longValueExact();
    }
}
