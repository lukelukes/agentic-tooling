package com.example.orders;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.lang.reflect.Method;
import org.junit.jupiter.api.Test;

class PricingCalculatorTest {
    private final PricingCalculator calc = new PricingCalculator();

    @Test
    void testPricing1() {
        Quote q = calc.quote(1000, 1, null);
        assertEquals(1000, q.subtotalCents());
        assertEquals(0, q.discountCents());
        assertEquals(1000, q.totalCents());
    }

    @Test
    void testPricing2() {
        Quote q = calc.quote(1000, 9, null);
        assertEquals(9000, q.subtotalCents());
        assertEquals(0, q.discountCents());
        assertEquals(9000, q.totalCents());
    }

    @Test
    void testPricing3() {
        Quote q = calc.quote(1000, 10, null);
        assertEquals(10000, q.subtotalCents());
        assertEquals(500, q.discountCents());
        assertEquals(9500, q.totalCents());
    }

    @Test
    void testPricing4() {
        Quote q = calc.quote(1000, 49, null);
        assertEquals(49000, q.subtotalCents());
        assertEquals(2450, q.discountCents());
        assertEquals(46550, q.totalCents());
    }

    @Test
    void testPricing5() {
        Quote q = calc.quote(1000, 50, null);
        assertEquals(50000, q.subtotalCents());
        assertEquals(5000, q.discountCents());
        assertEquals(45000, q.totalCents());
    }

    @Test
    void testPromo() {
        Quote q = calc.quote(1000, 2, "WELCOME10");
        assertEquals(1000, q.discountCents());
        assertEquals(1000, q.totalCents());
    }

    @Test
    void testManyQuantities() {
        for (int qty = 1; qty <= 60; qty++) {
            int pct;
            if (qty >= 50) {
                pct = 10;
            } else if (qty >= 10) {
                pct = 5;
            } else {
                pct = 0;
            }
            assertEquals(pct, calc.bulkDiscountPercent(qty));
        }
    }

    @Test
    void testRounding() throws Exception {
        Method m = PricingCalculator.class.getDeclaredMethod("roundHalfEven", long.class, long.class);
        m.setAccessible(true);
        assertEquals(2L, m.invoke(calc, 250L, 100L));
        assertEquals(4L, m.invoke(calc, 350L, 100L));
    }
}
