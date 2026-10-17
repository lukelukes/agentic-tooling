package signup

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
	"sync"
	"time"
	"unicode"
)

var (
	ErrInvalidEmail = errors.New("invalid email")
	ErrEmailTaken   = errors.New("email already registered")
	ErrInvalidToken = errors.New("invalid verification token")
	ErrTokenExpired = errors.New("verification token expired")
)

// WeakPasswordError lists every password rule that was violated.
type WeakPasswordError struct{ Problems []string }

func (e *WeakPasswordError) Error() string { return "weak password: " + strings.Join(e.Problems, ", ") }

type User struct {
	ID           string
	Email        string
	PasswordHash string
	Verified     bool
	CreatedAt    time.Time
}

// Hasher is an in-process password hasher.
type Hasher interface{ Hash(password string) string }

type SHA256Hasher struct{ Pepper string }

func (h SHA256Hasher) Hash(pw string) string {
	sum := sha256.Sum256([]byte(h.Pepper + pw))
	return "sha256:" + hex.EncodeToString(sum[:])
}

// Mailer sends e-mail through the external provider.
type Mailer interface {
	Send(ctx context.Context, to, subject, body string) error
}

type pendingToken struct {
	email   string
	expires time.Time
}

type Service struct {
	Store    UserStore
	Hasher   Hasher
	Mailer   Mailer
	TokenTTL time.Duration

	mu     sync.Mutex
	tokens map[string]pendingToken
}

func NewService(store UserStore, hasher Hasher, mailer Mailer) *Service {
	return &Service{Store: store, Hasher: hasher, Mailer: mailer, TokenTTL: 24 * time.Hour, tokens: map[string]pendingToken{}}
}

// normalizeEmail trims and lower-cases an address; e-mail addresses are
// unique case-insensitively.
func normalizeEmail(raw string) (string, error) {
	e := strings.ToLower(strings.TrimSpace(raw))
	local, domain, ok := strings.Cut(e, "@")
	if !ok || local == "" || strings.Contains(domain, "@") || !strings.Contains(domain, ".") ||
		strings.HasPrefix(domain, ".") || strings.HasSuffix(domain, ".") {
		return "", ErrInvalidEmail
	}
	return e, nil
}

// CheckPassword returns the violated rules, or nil if the password is acceptable.
// Rules: 10-72 bytes, at least one upper-case letter, one lower-case letter and
// one digit, and it must not contain the e-mail's local part (case-insensitive,
// only checked when the local part is at least 3 bytes; like the length rule,
// this counts bytes, so "éé" (4 bytes) is checked).
func CheckPassword(pw, email string) []string {
	var problems []string
	if len(pw) < 10 {
		problems = append(problems, "too short")
	}
	if len(pw) > 72 {
		problems = append(problems, "too long")
	}
	var upper, lower, digit bool
	for _, r := range pw {
		upper = upper || unicode.IsUpper(r)
		lower = lower || unicode.IsLower(r)
		digit = digit || unicode.IsDigit(r)
	}
	if !upper {
		problems = append(problems, "needs upper-case letter")
	}
	if !lower {
		problems = append(problems, "needs lower-case letter")
	}
	if !digit {
		problems = append(problems, "needs digit")
	}
	if local, _, _ := strings.Cut(strings.ToLower(email), "@"); len(local) >= 3 && strings.Contains(strings.ToLower(pw), local) {
		problems = append(problems, "contains e-mail name")
	}
	return problems
}

func buildWelcomeMessage(email, token string) string {
	return fmt.Sprintf("Welcome %s!\nConfirm your account: https://example.com/verify?token=%s\n", email, token)
}

func newToken() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

// Register creates an unverified user and e-mails a verification link.
// If the e-mail cannot be sent the user still exists and the error is returned.
func (s *Service) Register(ctx context.Context, rawEmail, password string) (User, error) {
	email, err := normalizeEmail(rawEmail)
	if err != nil {
		return User{}, err
	}
	if problems := CheckPassword(password, email); len(problems) > 0 {
		return User{}, &WeakPasswordError{Problems: problems}
	}
	if _, found, err := s.Store.FindByEmail(ctx, email); err != nil {
		return User{}, err
	} else if found {
		return User{}, ErrEmailTaken
	}
	u := User{ID: newToken()[:12], Email: email, PasswordHash: s.Hasher.Hash(password), CreatedAt: time.Now()}
	if err := s.Store.Save(ctx, u); err != nil {
		return User{}, err
	}
	token := newToken()
	s.mu.Lock()
	s.tokens[token] = pendingToken{email: email, expires: time.Now().Add(s.TokenTTL)}
	s.mu.Unlock()
	if err := s.Mailer.Send(ctx, email, "Confirm your account", buildWelcomeMessage(email, token)); err != nil {
		return u, fmt.Errorf("send welcome: %w", err)
	}
	return u, nil
}

// Verify marks the user owning token as verified. Tokens are single-use and
// expire TokenTTL after registration.
func (s *Service) Verify(ctx context.Context, token string) error {
	s.mu.Lock()
	p, ok := s.tokens[token]
	delete(s.tokens, token)
	s.mu.Unlock()
	if !ok {
		return ErrInvalidToken
	}
	if !time.Now().Before(p.expires) {
		return ErrTokenExpired
	}
	u, found, err := s.Store.FindByEmail(ctx, p.email)
	if err != nil {
		return err
	}
	if !found {
		return ErrInvalidToken
	}
	u.Verified = true
	return s.Store.Save(ctx, u)
}
