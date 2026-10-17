package com.example.library;

/**
 * Sends e-mail to members through the city's external SMTP relay.
 * Implementations may throw {@link NotificationFailedException} when the relay is unavailable.
 */
public interface MemberNotifier {
    void sendLateFeeNotice(LateFeeNotice notice);

    final class NotificationFailedException extends RuntimeException {
        public NotificationFailedException(String message) {
            super(message);
        }
    }
}
