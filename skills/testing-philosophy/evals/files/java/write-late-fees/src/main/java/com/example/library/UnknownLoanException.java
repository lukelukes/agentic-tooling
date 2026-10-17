package com.example.library;

public final class UnknownLoanException extends RuntimeException {
    public UnknownLoanException(String loanId) {
        super("unknown loan: " + loanId);
    }
}
