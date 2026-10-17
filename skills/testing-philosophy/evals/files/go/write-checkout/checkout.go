package checkout

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
	"time"
)

var (
	ErrInvalidRequest = errors.New("invalid request")
	ErrCouponExpired  = errors.New("coupon expired")
)

type Item struct {
	SKU string `json:"sku"`
	Qty int    `json:"qty"`
}

type Request struct {
	Email  string `json:"email"`
	Coupon string `json:"coupon,omitempty"`
	Items  []Item `json:"items"`
}

// Receipt is the e-mail sent to the customer after a successful checkout.
type Receipt struct {
	To         string
	OrderID    string
	TotalCents int64
}

// ReceiptSender delivers receipts through the external e-mail provider.
type ReceiptSender interface {
	SendReceipt(ctx context.Context, r Receipt) error
}

type Service struct {
	Store    Store
	Receipts ReceiptSender
	Now      func() time.Time
	NewID    func() string
}

func NewService(store Store, receipts ReceiptSender) *Service {
	return &Service{Store: store, Receipts: receipts, Now: time.Now, NewID: randomID}
}

func randomID() string {
	b := make([]byte, 8)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

// Checkout validates the request, prices it, reserves stock and records the
// order, then e-mails a receipt. Duplicate SKUs are merged before pricing.
// A failed receipt e-mail does not undo the order: the order is returned with
// ReceiptSent == false and no error, so it can be re-sent later.
func (s *Service) Checkout(ctx context.Context, req Request) (Order, error) {
	if !strings.Contains(req.Email, "@") || len(req.Items) == 0 {
		return Order{}, ErrInvalidRequest
	}
	qty := map[string]int{}
	var order []string
	for _, it := range req.Items {
		if it.Qty <= 0 {
			return Order{}, fmt.Errorf("%w: qty must be positive", ErrInvalidRequest)
		}
		if _, seen := qty[it.SKU]; !seen {
			order = append(order, it.SKU)
		}
		qty[it.SKU] += it.Qty
	}
	lines := make([]PricedLine, 0, len(order))
	for _, sku := range order {
		p, err := s.Store.Product(ctx, sku)
		if err != nil {
			return Order{}, err
		}
		lines = append(lines, PricedLine{SKU: sku, Qty: qty[sku], UnitCents: p.PriceCents})
	}
	now := s.Now()
	var coupon *Coupon
	if req.Coupon != "" {
		c, err := s.Store.Coupon(ctx, req.Coupon)
		if err != nil {
			return Order{}, err
		}
		if !now.Before(c.ExpiresAt) {
			return Order{}, ErrCouponExpired
		}
		coupon = &c
	}
	o := Order{ID: s.NewID(), Email: req.Email, Lines: lines, Totals: PriceOrder(lines, coupon), CreatedAt: now}
	if err := s.Store.PlaceOrder(ctx, o); err != nil {
		return Order{}, err
	}
	if err := s.Receipts.SendReceipt(ctx, Receipt{To: o.Email, OrderID: o.ID, TotalCents: o.Totals.TotalCents}); err != nil {
		return o, nil
	}
	if err := s.Store.MarkReceiptSent(ctx, o.ID); err != nil {
		return o, err
	}
	o.ReceiptSent = true
	return o, nil
}
