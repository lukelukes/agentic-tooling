package com.example.library;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;

/**
 * Library late-fee rules (all amounts in cents).
 *
 * <ul>
 *   <li>Returned on or before the due date: no fee.</li>
 *   <li>Grace period: 1 or 2 days late costs nothing.</li>
 *   <li>From 3 days late, every late day is charged (grace days included):
 *       25 cents per day for days 1-7, 50 cents per day for day 8 onward.</li>
 *   <li>STUDENT members pay half, rounded up to the next whole cent.</li>
 *   <li>The fee never exceeds the item's replacement cost (applied after the discount).</li>
 * </ul>
 */
public final class LateFeePolicy {
    static final int GRACE_DAYS = 2;
    static final int FIRST_TIER_DAYS = 7;
    static final long FIRST_TIER_RATE = 25;
    static final long SECOND_TIER_RATE = 50;

    public long daysLate(LocalDate dueOn, LocalDate returnedOn) {
        long days = ChronoUnit.DAYS.between(dueOn, returnedOn);
        return Math.max(0, days);
    }

    public long feeCents(LocalDate dueOn, LocalDate returnedOn, MemberType memberType, long replacementCostCents) {
        long late = daysLate(dueOn, returnedOn);
        if (late <= GRACE_DAYS) {
            return 0;
        }
        long firstTierDays = Math.min(late, FIRST_TIER_DAYS);
        long secondTierDays = Math.max(0, late - FIRST_TIER_DAYS);
        long fee = firstTierDays * FIRST_TIER_RATE + secondTierDays * SECOND_TIER_RATE;
        if (memberType == MemberType.STUDENT) {
            fee = (fee + 1) / 2;
        }
        return Math.min(fee, replacementCostCents);
    }
}
