package com.example.orders;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * This service's own orders database: the production implementation for the single-node
 * deployment (a managed dependency, not a test fake).
 */
public final class InMemoryOrderRepository implements OrderRepository {
    private final Map<String, Order> orders = new LinkedHashMap<>();

    @Override
    public synchronized void save(Order order) {
        orders.put(order.id(), order);
    }

    @Override
    public synchronized Optional<Order> find(String orderId) {
        return Optional.ofNullable(orders.get(orderId));
    }

    @Override
    public synchronized List<Order> findByCustomer(String customerId) {
        List<Order> result = new ArrayList<>();
        for (Order o : orders.values()) {
            if (o.customerId().equals(customerId)) {
                result.add(o);
            }
        }
        return result;
    }
}
