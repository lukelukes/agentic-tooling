package com.example.orders;

public record OrderLine(String sku, int quantity, long unitPriceCents) {}
