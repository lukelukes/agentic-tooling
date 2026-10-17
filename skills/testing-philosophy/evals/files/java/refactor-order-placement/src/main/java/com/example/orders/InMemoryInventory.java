package com.example.orders;

import java.util.HashMap;
import java.util.Map;

/**
 * This service's own stock database: the production implementation for the single-node
 * deployment (a managed dependency, not a test fake).
 */
public final class InMemoryInventory implements InventoryRepository {
    private final Map<String, Integer> stock = new HashMap<>();
    private final Map<String, Long> prices = new HashMap<>();

    public InMemoryInventory add(String sku, int quantity, long unitPriceCents) {
        stock.put(sku, quantity);
        prices.put(sku, unitPriceCents);
        return this;
    }

    @Override
    public synchronized int available(String sku) {
        return stock.getOrDefault(sku, 0);
    }

    @Override
    public long unitPriceCents(String sku) {
        Long price = prices.get(sku);
        if (price == null) {
            throw new IllegalArgumentException("unknown sku: " + sku);
        }
        return price;
    }

    @Override
    public synchronized boolean reserve(String sku, int quantity) {
        int have = stock.getOrDefault(sku, 0);
        if (have < quantity) {
            return false;
        }
        stock.put(sku, have - quantity);
        return true;
    }

    @Override
    public synchronized void release(String sku, int quantity) {
        stock.merge(sku, quantity, Integer::sum);
    }
}
