package checkout

import (
	"context"
	"errors"
	"sync"
	"time"
)

var (
	ErrUnknownSKU    = errors.New("unknown sku")
	ErrOutOfStock    = errors.New("out of stock")
	ErrUnknownCoupon = errors.New("unknown coupon")
	ErrNotFound      = errors.New("not found")
)

type Product struct {
	SKU        string
	PriceCents int64
	Stock      int
}

type Coupon struct {
	Code             string
	PercentOff       int
	MinSubtotalCents int64
	ExpiresAt        time.Time // the coupon is no longer valid at or after this instant
}

type Order struct {
	ID          string
	Email       string
	Lines       []PricedLine
	Totals      Totals
	CreatedAt   time.Time
	ReceiptSent bool
}

// Store is the application's own database. MemoryStore is the production
// implementation used by the single-node deployment.
type Store interface {
	Product(ctx context.Context, sku string) (Product, error)
	Coupon(ctx context.Context, code string) (Coupon, error)
	// PlaceOrder atomically decrements stock for every line and saves the
	// order. If any line lacks stock, nothing changes and ErrOutOfStock is returned.
	PlaceOrder(ctx context.Context, o Order) error
	MarkReceiptSent(ctx context.Context, orderID string) error
	Order(ctx context.Context, id string) (Order, error)
}

type MemoryStore struct {
	mu       sync.Mutex
	products map[string]Product
	coupons  map[string]Coupon
	orders   map[string]Order
}

func NewMemoryStore(products []Product, coupons []Coupon) *MemoryStore {
	s := &MemoryStore{products: map[string]Product{}, coupons: map[string]Coupon{}, orders: map[string]Order{}}
	for _, p := range products {
		s.products[p.SKU] = p
	}
	for _, c := range coupons {
		s.coupons[c.Code] = c
	}
	return s
}

func (s *MemoryStore) Product(_ context.Context, sku string) (Product, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	p, ok := s.products[sku]
	if !ok {
		return Product{}, ErrUnknownSKU
	}
	return p, nil
}

func (s *MemoryStore) Coupon(_ context.Context, code string) (Coupon, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	c, ok := s.coupons[code]
	if !ok {
		return Coupon{}, ErrUnknownCoupon
	}
	return c, nil
}

func (s *MemoryStore) PlaceOrder(_ context.Context, o Order) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, l := range o.Lines {
		if s.products[l.SKU].Stock < l.Qty {
			return ErrOutOfStock
		}
	}
	for _, l := range o.Lines {
		p := s.products[l.SKU]
		p.Stock -= l.Qty
		s.products[l.SKU] = p
	}
	s.orders[o.ID] = o
	return nil
}

func (s *MemoryStore) MarkReceiptSent(_ context.Context, id string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	o, ok := s.orders[id]
	if !ok {
		return ErrNotFound
	}
	o.ReceiptSent = true
	s.orders[id] = o
	return nil
}

func (s *MemoryStore) Order(_ context.Context, id string) (Order, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	o, ok := s.orders[id]
	if !ok {
		return Order{}, ErrNotFound
	}
	return o, nil
}
