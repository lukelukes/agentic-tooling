package com.example.orders;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.time.Instant;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class OrderControllerTest {
    private OrderService service;
    private OrderController controller;

    @BeforeEach
    void setUp() {
        service = mock(OrderService.class);
        controller = new OrderController(service);
    }

    @Test
    void test1() {
        PlaceOrderResponse r = controller.placeOrder(new PlaceOrderRequest(" ", "SKU-1", 1, null, "tok"));
        assertEquals(400, r.status());
        verifyNoInteractions(service);
    }

    @Test
    void testQuantityZero() {
        PlaceOrderResponse r = controller.placeOrder(new PlaceOrderRequest("c-1", "SKU-1", 0, null, "tok"));
        assertEquals(400, r.status());
        assertEquals("quantity must be between 1 and 500", r.error());
        verifyNoInteractions(service);
    }

    @Test
    void testQuantityNegative() {
        PlaceOrderResponse r = controller.placeOrder(new PlaceOrderRequest("c-1", "SKU-1", -1, null, "tok"));
        assertEquals(400, r.status());
        assertEquals("quantity must be between 1 and 500", r.error());
        verifyNoInteractions(service);
    }

    @Test
    void testPlaceOrderWorks() {
        Order order = new Order("o-1", "c-1", new OrderLine("SKU-1", 2, 617), 1234, "pay-1", Instant.EPOCH);
        when(service.place(anyString(), anyString(), anyInt(), any(), anyString())).thenReturn(order);

        PlaceOrderResponse r = controller.placeOrder(new PlaceOrderRequest("c-1", "SKU-1", 2, null, "tok"));

        assertEquals(201, r.status());
        assertEquals("o-1", r.orderId());
        assertEquals(1234, r.totalCents());
        assertNull(r.error());
        verify(service).place("c-1", "SKU-1", 2, null, "tok");
    }

    @Test
    void testOutOfStock() {
        when(service.place(anyString(), anyString(), anyInt(), any(), anyString()))
                .thenThrow(new OrderService.OutOfStockException("SKU-1"));

        PlaceOrderResponse r = controller.placeOrder(new PlaceOrderRequest("c-1", "SKU-1", 2, null, "tok"));

        assertEquals(409, r.status());
        verify(service).place("c-1", "SKU-1", 2, null, "tok");
    }
}
