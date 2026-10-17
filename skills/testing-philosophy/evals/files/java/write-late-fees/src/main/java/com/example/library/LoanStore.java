package com.example.library;

import java.util.Optional;

/** Persistence for loans. Owned by this service; no other system reads it. */
public interface LoanStore {
    Optional<Loan> find(String loanId);

    void save(Loan loan);
}
