package com.example.library;

import java.time.LocalDate;
import java.util.Objects;

/** A single book loan. {@code returnedOn} is null while the book is still out. */
public record Loan(
        String id,
        String memberEmail,
        MemberType memberType,
        long replacementCostCents,
        LocalDate checkedOutOn,
        LocalDate dueOn,
        LocalDate returnedOn,
        long feeCents) {

    public Loan {
        Objects.requireNonNull(id, "id");
        Objects.requireNonNull(memberEmail, "memberEmail");
        Objects.requireNonNull(memberType, "memberType");
        Objects.requireNonNull(checkedOutOn, "checkedOutOn");
        Objects.requireNonNull(dueOn, "dueOn");
        if (replacementCostCents <= 0) {
            throw new IllegalArgumentException("replacementCostCents must be positive");
        }
    }

    public boolean isReturned() {
        return returnedOn != null;
    }

    public Loan returned(LocalDate on, long fee) {
        return new Loan(id, memberEmail, memberType, replacementCostCents, checkedOutOn, dueOn, on, fee);
    }
}
