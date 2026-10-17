package com.example.orders;

/** Stock levels, stored in this service's own database; InMemoryInventory is the production implementation. */
public interface InventoryRepository {
    int available(String sku);

    long unitPriceCents(String sku);

    /** Atomically decrements stock; returns false (and changes nothing) if not enough is available. */
    boolean reserve(String sku, int quantity);

    void release(String sku, int quantity);
}
