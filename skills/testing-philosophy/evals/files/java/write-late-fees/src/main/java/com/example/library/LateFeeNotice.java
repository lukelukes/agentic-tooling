package com.example.library;

public record LateFeeNotice(String to, String loanId, long daysLate, long feeCents) {}
