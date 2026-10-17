package com.example.library;

import java.time.Clock;
import java.time.LocalDate;
import java.util.Objects;

/**
 * Public entry point for the circulation desk: check books out and take them back.
 * "Today" is the calendar date of the injected clock in the clock's zone (the library's local time).
 */
public final class CirculationService {
    static final int LOAN_PERIOD_DAYS = 21;

    private final LoanStore store;
    private final MemberNotifier notifier;
    private final LateFeePolicy policy;
    private final Clock clock;

    public CirculationService(LoanStore store, MemberNotifier notifier, LateFeePolicy policy, Clock clock) {
        this.store = Objects.requireNonNull(store);
        this.notifier = Objects.requireNonNull(notifier);
        this.policy = Objects.requireNonNull(policy);
        this.clock = Objects.requireNonNull(clock);
    }

    public Loan checkOut(String loanId, String memberEmail, MemberType memberType, long replacementCostCents) {
        if (store.find(loanId).isPresent()) {
            throw new IllegalStateException("loan already exists: " + loanId);
        }
        LocalDate today = LocalDate.now(clock);
        Loan loan = new Loan(loanId, memberEmail, memberType, replacementCostCents,
                today, today.plusDays(LOAN_PERIOD_DAYS), null, 0);
        store.save(loan);
        return loan;
    }

    /**
     * Records the return, persists the fee, and e-mails a notice when a fee is due.
     * The return is persisted before the e-mail is attempted; if the relay fails the return still
     * stands and the receipt reports {@code noticeSent == false}. Returning twice is rejected.
     */
    public ReturnReceipt returnBook(String loanId) {
        Loan loan = store.find(loanId).orElseThrow(() -> new UnknownLoanException(loanId));
        if (loan.isReturned()) {
            throw new IllegalStateException("loan already returned: " + loanId);
        }
        LocalDate today = LocalDate.now(clock);
        long daysLate = policy.daysLate(loan.dueOn(), today);
        long fee = policy.feeCents(loan.dueOn(), today, loan.memberType(), loan.replacementCostCents());
        store.save(loan.returned(today, fee));

        boolean noticeSent = false;
        if (fee > 0) {
            try {
                notifier.sendLateFeeNotice(new LateFeeNotice(loan.memberEmail(), loanId, daysLate, fee));
                noticeSent = true;
            } catch (MemberNotifier.NotificationFailedException e) {
                noticeSent = false;
            }
        }
        return new ReturnReceipt(loanId, today, daysLate, fee, noticeSent);
    }
}
