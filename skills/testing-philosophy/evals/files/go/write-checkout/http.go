package checkout

import (
	"encoding/json"
	"errors"
	"net/http"
)

type orderResponse struct {
	ID            string `json:"id"`
	SubtotalCents int64  `json:"subtotal_cents"`
	DiscountCents int64  `json:"discount_cents"`
	ShippingCents int64  `json:"shipping_cents"`
	TotalCents    int64  `json:"total_cents"`
	ReceiptSent   bool   `json:"receipt_sent"`
}

// NewHandler exposes POST /orders.
//
//	201 order created        400 malformed or invalid request
//	409 insufficient stock   422 unknown SKU, unknown or expired coupon
func NewHandler(svc *Service) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /orders", func(w http.ResponseWriter, r *http.Request) {
		var req Request
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "malformed json", http.StatusBadRequest)
			return
		}
		o, err := svc.Checkout(r.Context(), req)
		switch {
		case errors.Is(err, ErrInvalidRequest):
			http.Error(w, err.Error(), http.StatusBadRequest)
		case errors.Is(err, ErrOutOfStock):
			http.Error(w, err.Error(), http.StatusConflict)
		case errors.Is(err, ErrUnknownSKU), errors.Is(err, ErrUnknownCoupon), errors.Is(err, ErrCouponExpired):
			http.Error(w, err.Error(), http.StatusUnprocessableEntity)
		case err != nil:
			http.Error(w, "internal error", http.StatusInternalServerError)
		default:
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusCreated)
			_ = json.NewEncoder(w).Encode(orderResponse{
				ID: o.ID, SubtotalCents: o.Totals.SubtotalCents, DiscountCents: o.Totals.DiscountCents,
				ShippingCents: o.Totals.ShippingCents, TotalCents: o.Totals.TotalCents, ReceiptSent: o.ReceiptSent,
			})
		}
	})
	return mux
}
