package com.example.orders;

import java.util.List;
import java.util.Optional;

/** Orders table in this service's own database; InMemoryOrderRepository is the production implementation. */
public interface OrderRepository {
    void save(Order order);

    Optional<Order> find(String orderId);

    List<Order> findByCustomer(String customerId);
}
