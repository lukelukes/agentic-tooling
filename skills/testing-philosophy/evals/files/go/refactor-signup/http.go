package signup

import (
	"encoding/json"
	"errors"
	"net/http"
)

// NewHandler exposes the signup feature over HTTP.
//
//	POST /signup {"email","password"}  201 {"id","email"} | 400 invalid email or weak password | 409 taken
//	GET  /verify?token=...             204 | 400 invalid token | 410 expired token
func NewHandler(svc *Service) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /signup", func(w http.ResponseWriter, r *http.Request) {
		var body struct{ Email, Password string }
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			http.Error(w, "malformed json", http.StatusBadRequest)
			return
		}
		u, err := svc.Register(r.Context(), body.Email, body.Password)
		var weak *WeakPasswordError
		switch {
		case errors.Is(err, ErrInvalidEmail), errors.As(err, &weak):
			http.Error(w, err.Error(), http.StatusBadRequest)
		case errors.Is(err, ErrEmailTaken):
			http.Error(w, err.Error(), http.StatusConflict)
		case err != nil && u.ID == "":
			http.Error(w, "internal error", http.StatusInternalServerError)
		default: // created, even if the welcome e-mail failed
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusCreated)
			_ = json.NewEncoder(w).Encode(map[string]string{"id": u.ID, "email": u.Email})
		}
	})
	mux.HandleFunc("GET /verify", func(w http.ResponseWriter, r *http.Request) {
		switch err := svc.Verify(r.Context(), r.URL.Query().Get("token")); {
		case errors.Is(err, ErrInvalidToken):
			http.Error(w, err.Error(), http.StatusBadRequest)
		case errors.Is(err, ErrTokenExpired):
			http.Error(w, err.Error(), http.StatusGone)
		case err != nil:
			http.Error(w, "internal error", http.StatusInternalServerError)
		default:
			w.WriteHeader(http.StatusNoContent)
		}
	})
	return mux
}
