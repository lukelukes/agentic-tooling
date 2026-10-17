package com.example.orders;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Clock;
import java.time.Instant;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.InOrder;

class OrderServiceTest {
    private InventoryRepository inventory;
    private PricingCalculator pricing;
    private OrderRepository orders;
    private PaymentGateway payments;
    private OrderService service;

    @BeforeEach
    void setUp() {
        inventory = mock(InventoryRepository.class);
        pricing = mock(PricingCalculator.class);
        orders = mock(OrderRepository.class);
        payments = mock(PaymentGateway.class);
        service = new OrderService(inventory, pricing, orders, payments, Clock.systemUTC(), () -> "o-1");

        when(inventory.available("SKU-1")).thenReturn(100);
        when(inventory.reserve("SKU-1", 3)).thenReturn(true);
        when(inventory.unitPriceCents("SKU-1")).thenReturn(2000L);
        when(pricing.quote(2000L, 3, null)).thenReturn(new Quote(6000, 0, 6000));
        when(payments.charge(anyString(), anyLong(), anyString())).thenReturn("pay-1");
    }

    @Test
    void testPlaceOrder() {
        service.place("c-1", "SKU-1", 3, null, "tok");

        InOrder inOrder = inOrder(inventory, pricing, payments, orders);
        inOrder.verify(inventory).available("SKU-1");
        inOrder.verify(inventory).reserve("SKU-1", 3);
        inOrder.verify(inventory).unitPriceCents("SKU-1");
        inOrder.verify(pricing).quote(2000L, 3, null);
        inOrder.verify(payments).charge("tok", 6000L, "o-1");
        inOrder.verify(orders).save(any(Order.class));
    }

    @Test
    void testChecksAvailabilityFirst() {
        service.place("c-1", "SKU-1", 3, null, "tok");

        verify(inventory, times(1)).available("SKU-1");
        verify(inventory, times(1)).reserve("SKU-1", 3);
    }

    @Test
    void testTotal() {
        when(pricing.quote(2000L, 3, null)).thenReturn(new Quote(6000, 600, 5400));

        Order order = service.place("c-1", "SKU-1", 3, null, "tok");

        assertEquals(5400, order.totalCents());
        verify(pricing).quote(2000L, 3, null);
    }

    @Test
    void testSavesOrder() {
        service.place("c-1", "SKU-1", 3, null, "tok");

        ArgumentCaptor<Order> captor = ArgumentCaptor.forClass(Order.class);
        verify(orders).save(captor.capture());
        assertEquals("o-1", captor.getValue().id());
        assertEquals("c-1", captor.getValue().customerId());
        assertEquals("pay-1", captor.getValue().paymentId());
        assertEquals(3, captor.getValue().line().quantity());
    }

    @Test
    void testTimestamp() throws InterruptedException {
        Instant before = Instant.now();
        Thread.sleep(20);
        Order order = service.place("c-1", "SKU-1", 3, null, "tok");
        Thread.sleep(20);
        Instant after = Instant.now();

        assertTrue(order.placedAt().isAfter(before));
        assertTrue(order.placedAt().isBefore(after));
    }

    @Test
    void testNoStock() {
        when(inventory.available("SKU-1")).thenReturn(2);

        assertThrows(OrderService.OutOfStockException.class,
                () -> service.place("c-1", "SKU-1", 3, null, "tok"));

        verify(inventory, never()).reserve(anyString(), anyInt());
        verify(payments, never()).charge(anyString(), anyLong(), anyString());
        verify(orders, never()).save(any());
    }

    @Test
    void testReserveFails() {
        when(inventory.reserve("SKU-1", 3)).thenReturn(false);

        boolean thrown = false;
        try {
            service.place("c-1", "SKU-1", 3, null, "tok");
        } catch (OrderService.OutOfStockException e) {
            thrown = true;
        }
        assertTrue(thrown);
        assertFalse(!thrown);
        verify(payments, never()).charge(anyString(), anyLong(), anyString());
    }
}
