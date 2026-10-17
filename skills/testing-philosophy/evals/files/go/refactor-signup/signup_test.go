package signup_test

import (
	"context"
	"errors"
	"reflect"
	"strings"
	"testing"
	"time"

	"example.com/signup"
)

// ---- hand-written mocks ----

type mockStore struct {
	findResult    bool
	findUser      signup.User
	findCalls     int
	lastFindEmail string
	saveCalls     int
	saved         []signup.User
	log           *[]string
}

func (m *mockStore) FindByEmail(_ context.Context, email string) (signup.User, bool, error) {
	m.findCalls++
	m.lastFindEmail = email
	if m.log != nil {
		*m.log = append(*m.log, "find")
	}
	return m.findUser, m.findResult, nil
}

func (m *mockStore) Save(_ context.Context, u signup.User) error {
	m.saveCalls++
	m.saved = append(m.saved, u)
	if m.log != nil {
		*m.log = append(*m.log, "save")
	}
	return nil
}

type mockHasher struct {
	hashCalls    int
	lastPassword string
	log          *[]string
}

func (m *mockHasher) Hash(pw string) string {
	m.hashCalls++
	m.lastPassword = pw
	if m.log != nil {
		*m.log = append(*m.log, "hash")
	}
	return "hashed:" + pw
}

type sentMail struct{ to, subject, body string }

type mockMailer struct {
	sent []sentMail
	log  *[]string
}

func (m *mockMailer) Send(_ context.Context, to, subject, body string) error {
	m.sent = append(m.sent, sentMail{to, subject, body})
	if m.log != nil {
		*m.log = append(*m.log, "send")
	}
	return nil
}

func tokenFrom(body string) string {
	_, tok, _ := strings.Cut(body, "token=")
	return strings.TrimSpace(tok)
}

// ---- tests ----

func TestRegister1(t *testing.T) {
	store := &mockStore{}
	hasher := &mockHasher{}
	mailer := &mockMailer{}
	svc := signup.NewService(store, hasher, mailer)

	u, err := svc.Register(context.Background(), " Bob@Example.com ", "Correct-Horse-9")
	if err != nil {
		t.Fatal(err)
	}
	if store.findCalls != 1 {
		t.Errorf("findCalls = %d", store.findCalls)
	}
	if store.lastFindEmail != "bob@example.com" {
		t.Errorf("lastFindEmail = %q", store.lastFindEmail)
	}
	if store.saveCalls != 1 {
		t.Errorf("saveCalls = %d", store.saveCalls)
	}
	if hasher.hashCalls != 1 || hasher.lastPassword != "Correct-Horse-9" {
		t.Errorf("hasher not called correctly: %d %q", hasher.hashCalls, hasher.lastPassword)
	}
	if u.PasswordHash != "hashed:Correct-Horse-9" {
		t.Errorf("PasswordHash = %q", u.PasswordHash)
	}
	if len(mailer.sent) != 1 {
		t.Errorf("sent %d mails", len(mailer.sent))
	}
}

func TestRegister2(t *testing.T) {
	store := &mockStore{findResult: true}
	hasher := &mockHasher{}
	mailer := &mockMailer{}
	svc := signup.NewService(store, hasher, mailer)

	_, err := svc.Register(context.Background(), "bob@example.com", "Correct-Horse-9")
	if err != signup.ErrEmailTaken {
		t.Errorf("err = %v", err)
	}
	if store.saveCalls != 0 {
		t.Errorf("saveCalls = %d", store.saveCalls)
	}
	if hasher.hashCalls != 0 {
		t.Errorf("hashCalls = %d", hasher.hashCalls)
	}
	if len(mailer.sent) != 0 {
		t.Errorf("sent %d mails", len(mailer.sent))
	}
}

func TestRegisterCallsCollaboratorsInOrder(t *testing.T) {
	var log []string
	svc := signup.NewService(&mockStore{log: &log}, &mockHasher{log: &log}, &mockMailer{log: &log})

	if _, err := svc.Register(context.Background(), "carol@example.com", "Correct-Horse-9"); err != nil {
		t.Fatal(err)
	}
	want := []string{"find", "hash", "save", "send"}
	if !reflect.DeepEqual(log, want) {
		t.Errorf("call order = %v, want %v", log, want)
	}
}

func TestPasswordTooShort(t *testing.T) {
	svc := signup.NewService(&mockStore{}, &mockHasher{}, &mockMailer{})
	_, err := svc.Register(context.Background(), "dave@example.com", "Short9x")
	var weak *signup.WeakPasswordError
	if !errors.As(err, &weak) {
		t.Fatalf("err = %v", err)
	}
	if weak.Problems[0] != "too short" {
		t.Errorf("problems = %v", weak.Problems)
	}
}

func TestPasswordNoDigit(t *testing.T) {
	svc := signup.NewService(&mockStore{}, &mockHasher{}, &mockMailer{})
	_, err := svc.Register(context.Background(), "dave@example.com", "NoDigitsHereAtAll")
	var weak *signup.WeakPasswordError
	if !errors.As(err, &weak) {
		t.Fatalf("err = %v", err)
	}
	if weak.Problems[0] != "needs digit" {
		t.Errorf("problems = %v", weak.Problems)
	}
}

func TestPasswordNoUpper(t *testing.T) {
	svc := signup.NewService(&mockStore{}, &mockHasher{}, &mockMailer{})
	_, err := svc.Register(context.Background(), "dave@example.com", "no-upper-case-9")
	var weak *signup.WeakPasswordError
	if !errors.As(err, &weak) {
		t.Fatalf("err = %v", err)
	}
	if weak.Problems[0] != "needs upper-case letter" {
		t.Errorf("problems = %v", weak.Problems)
	}
}

func TestPasswordNoLower(t *testing.T) {
	svc := signup.NewService(&mockStore{}, &mockHasher{}, &mockMailer{})
	_, err := svc.Register(context.Background(), "dave@example.com", "NO-LOWER-CASE-9")
	var weak *signup.WeakPasswordError
	if !errors.As(err, &weak) {
		t.Fatalf("err = %v", err)
	}
	if weak.Problems[0] != "needs lower-case letter" {
		t.Errorf("problems = %v", weak.Problems)
	}
}

func TestNormalizeEmail(t *testing.T) {
	inputs := []string{" Alice@Example.COM", "bob@example.com", "no-at-sign.com", "x@nodot"}
	for _, in := range inputs {
		got, err := signup.NormalizeEmailForTest(in)
		want := strings.ToLower(strings.TrimSpace(in))
		if !strings.Contains(in, "@") || !strings.Contains(strings.SplitN(in, "@", 2)[1], ".") {
			if err == nil {
				t.Errorf("expected error for %q", in)
			}
			continue
		}
		if got != want {
			t.Errorf("got %q want %q", got, want)
		}
	}
}

func TestWelcomeMessage(t *testing.T) {
	got := signup.BuildWelcomeMessageForTest("erin@example.com", "abc123")
	want := "Welcome erin@example.com!\nConfirm your account: https://example.com/verify?token=abc123\n"
	if got != want {
		t.Errorf("got %q", got)
	}
}

func TestVerifyDeletesToken(t *testing.T) {
	store := &mockStore{findResult: true, findUser: signup.User{ID: "u1", Email: "frank@example.com"}}
	mailer := &mockMailer{}
	svc := signup.NewService(store, &mockHasher{}, mailer)
	store.findResult = false
	if _, err := svc.Register(context.Background(), "frank@example.com", "Correct-Horse-9"); err != nil {
		t.Fatal(err)
	}
	store.findResult = true

	if err := svc.Verify(context.Background(), tokenFrom(mailer.sent[0].body)); err != nil {
		t.Fatal(err)
	}
	tokens := reflect.ValueOf(svc).Elem().FieldByName("tokens")
	if tokens.Len() != 0 {
		t.Errorf("tokens map has %d entries", tokens.Len())
	}
	if store.saveCalls != 2 || !store.saved[1].Verified {
		t.Errorf("user not saved as verified")
	}
}

func TestTokenExpiry(t *testing.T) {
	store := &mockStore{}
	mailer := &mockMailer{}
	svc := signup.NewService(store, &mockHasher{}, mailer)
	svc.TokenTTL = 20 * time.Millisecond
	if _, err := svc.Register(context.Background(), "gina@example.com", "Correct-Horse-9"); err != nil {
		t.Fatal(err)
	}
	time.Sleep(50 * time.Millisecond)
	if err := svc.Verify(context.Background(), tokenFrom(mailer.sent[0].body)); err != signup.ErrTokenExpired {
		t.Errorf("err = %v", err)
	}
}

func TestItWorks(t *testing.T) {
	svc := signup.NewService(&mockStore{}, signup.SHA256Hasher{Pepper: "p"}, &mockMailer{})
	u, err := svc.Register(context.Background(), "hank@example.com", "Correct-Horse-9")
	if err != nil || u.ID == "" || !strings.HasPrefix(u.PasswordHash, "sha256:") || len(u.PasswordHash) != 71 {
		t.Errorf("bad user %+v %v", u, err)
	}
}
