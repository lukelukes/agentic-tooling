package com.example.orders;

/** Inbound payload of POST /orders. {@code promoCode} may be null. */
public record PlaceOrderRequest(String customerId, String sku, int quantity, String promoCode, String cardToken) {}
