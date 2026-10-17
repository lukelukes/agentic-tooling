package com.example.orders;

import java.time.Instant;

public record Order(String id, String customerId, OrderLine line, long totalCents, String paymentId, Instant placedAt) {}
