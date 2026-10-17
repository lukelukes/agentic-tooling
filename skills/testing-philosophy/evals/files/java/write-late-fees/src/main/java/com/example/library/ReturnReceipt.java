package com.example.library;

import java.time.LocalDate;

public record ReturnReceipt(String loanId, LocalDate returnedOn, long daysLate, long feeCents, boolean noticeSent) {}
