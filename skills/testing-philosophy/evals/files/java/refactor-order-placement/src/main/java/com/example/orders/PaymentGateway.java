package com.example.orders;

/** Third-party card processor reached over HTTPS. */
public interface PaymentGateway {
    /** Returns the processor's payment id, or throws {@link PaymentDeclinedException}. */
    String charge(String cardToken, long amountCents, String idempotencyKey);

    final class PaymentDeclinedException extends RuntimeException {
        public PaymentDeclinedException(String reason) {
            super(reason);
        }
    }
}
