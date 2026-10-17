package signup

import (
	"context"
	"sync"
)

// UserStore is the application's own user database. MemoryUserStore is the
// production implementation for the single-node deployment.
type UserStore interface {
	FindByEmail(ctx context.Context, email string) (User, bool, error)
	Save(ctx context.Context, u User) error
}

type MemoryUserStore struct {
	mu    sync.Mutex
	users map[string]User // keyed by normalized e-mail
}

func NewMemoryUserStore() *MemoryUserStore { return &MemoryUserStore{users: map[string]User{}} }

func (s *MemoryUserStore) FindByEmail(_ context.Context, email string) (User, bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	u, ok := s.users[email]
	return u, ok, nil
}

func (s *MemoryUserStore) Save(_ context.Context, u User) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.users[u.Email] = u
	return nil
}
