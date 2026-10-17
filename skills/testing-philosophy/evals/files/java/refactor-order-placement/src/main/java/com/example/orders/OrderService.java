package com.example.orders;

import java.time.Clock;
import java.time.Instant;
import java.util.function.Supplier;

public class OrderService {
    private final InventoryRepository inventory;
    private final PricingCalculator pricing;
    private final OrderRepository orders;
    private final PaymentGateway payments;
    private final Clock clock;
    private final Supplier<String> ids;

    public OrderService(InventoryRepository inventory, PricingCalculator pricing, OrderRepository orders,
                        PaymentGateway payments, Clock clock, Supplier<String> ids) {
        this.inventory = inventory;
        this.pricing = pricing;
        this.orders = orders;
        this.payments = payments;
        this.clock = clock;
        this.ids = ids;
    }

    /**
     * Reserves stock, prices the order, charges the card and records the order.
     * If the charge is declined the reserved stock is released and nothing is recorded.
     */
    public Order place(String customerId, String sku, int quantity, String promoCode, String cardToken) {
        if (inventory.available(sku) < quantity) {
            throw new OutOfStockException(sku);
        }
        if (!inventory.reserve(sku, quantity)) {
            throw new OutOfStockException(sku);
        }
        long unitPrice = inventory.unitPriceCents(sku);
        Quote quote = pricing.quote(unitPrice, quantity, promoCode);
        String orderId = ids.get();
        String paymentId;
        try {
            paymentId = payments.charge(cardToken, quote.totalCents(), orderId);
        } catch (PaymentGateway.PaymentDeclinedException e) {
            inventory.release(sku, quantity);
            throw e;
        }
        Order order = new Order(orderId, customerId, new OrderLine(sku, quantity, unitPrice),
                quote.totalCents(), paymentId, Instant.now(clock));
        orders.save(order);
        return order;
    }

    public static final class OutOfStockException extends RuntimeException {
        public OutOfStockException(String sku) {
            super("out of stock: " + sku);
        }
    }
}
