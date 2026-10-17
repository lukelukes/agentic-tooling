package com.example.orders;

/** HTTP-style response: status 201, 400, 402 (payment declined) or 409 (out of stock). */
public record PlaceOrderResponse(int status, String orderId, long totalCents, String error) {
    static PlaceOrderResponse created(String orderId, long totalCents) {
        return new PlaceOrderResponse(201, orderId, totalCents, null);
    }

    static PlaceOrderResponse error(int status, String message) {
        return new PlaceOrderResponse(status, null, 0, message);
    }
}
