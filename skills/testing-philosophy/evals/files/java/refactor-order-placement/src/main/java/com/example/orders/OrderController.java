package com.example.orders;

/** Handler for POST /orders. Validates input and maps domain outcomes to HTTP statuses. */
public class OrderController {
    private final OrderService service;

    public OrderController(OrderService service) {
        this.service = service;
    }

    public PlaceOrderResponse placeOrder(PlaceOrderRequest request) {
        if (request.customerId() == null || request.customerId().isBlank()) {
            return PlaceOrderResponse.error(400, "customerId is required");
        }
        if (request.quantity() < 1 || request.quantity() > 500) {
            return PlaceOrderResponse.error(400, "quantity must be between 1 and 500");
        }
        try {
            Order order = service.place(request.customerId(), request.sku(), request.quantity(),
                    request.promoCode(), request.cardToken());
            return PlaceOrderResponse.created(order.id(), order.totalCents());
        } catch (OrderService.OutOfStockException e) {
            return PlaceOrderResponse.error(409, e.getMessage());
        } catch (PaymentGateway.PaymentDeclinedException e) {
            return PlaceOrderResponse.error(402, "payment declined: " + e.getMessage());
        }
    }
}
