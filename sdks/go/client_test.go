package starlock

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"
	"time"
)

const testSecret = "ss_example_for_sdk_tests_only"

type fixtures struct {
	SiteKey      string             `json:"site_key"`
	Session      Session            `json:"session"`
	Verification VerificationResult `json:"verification"`
	Failure      Error              `json:"error"`
}

func loadFixtures(t *testing.T) fixtures {
	t.Helper()
	raw, err := os.ReadFile("testdata/server-sdk.json")
	if err != nil {
		t.Fatal(err)
	}
	var data fixtures
	if err := json.Unmarshal(raw, &data); err != nil {
		t.Fatal(err)
	}
	return data
}

func clientFor(t *testing.T, address string) *Client {
	t.Helper()
	client, err := NewClient(Config{APIBase: address, SiteKey: "site_sdk_test", SiteSecret: testSecret})
	if err != nil {
		t.Fatal(err)
	}
	return client
}

func TestProtocolAndBinding(t *testing.T) {
	data := loadFixtures(t)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.Header.Get("Authorization") != "Bearer "+testSecret || r.Header.Get("Content-Type") != "application/json" {
			t.Error("incorrect request method or authentication headers")
		}
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Error(err)
		}
		if body["site_key"] != data.SiteKey || body["action"] != "login" || body["context_id"] != data.Verification.ContextID {
			t.Error("incorrect site/action/context binding")
		}
		switch r.URL.Path {
		case "/starlock/v1/sessions":
			if body["challenge_type"] != "rotate" || body["rotation_source"] != "preset" || body["image_set_id"] != "system-orbit" {
				t.Error("missing challenge options")
			}
			w.WriteHeader(http.StatusCreated)
			json.NewEncoder(w).Encode(data.Session)
		case "/starlock/v1/siteverify":
			if body["token"] != "token.example" {
				t.Error("missing verification token")
			}
			json.NewEncoder(w).Encode(data.Verification)
		default:
			t.Error("API path prefix was lost")
			w.WriteHeader(404)
		}
	}))
	defer server.Close()
	client := clientFor(t, server.URL+"/starlock/")
	session, err := client.CreateSession(context.Background(), SessionRequest{Action: "login", ContextID: data.Verification.ContextID,
		Origin: "https://app.example.com", ChallengeType: Rotate, RotationSource: "preset", ImageSetID: "system-orbit"})
	if err != nil || session == nil || *session != data.Session {
		t.Fatalf("session failed: %v", err)
	}
	result, err := client.SiteVerify(context.Background(), VerifyRequest{Token: "token.example", Action: "login", ContextID: data.Verification.ContextID})
	if err != nil || result == nil || *result != data.Verification {
		t.Fatalf("verification failed: %v", err)
	}
	if strings.Contains(fmt.Sprintf("%+v %#v %+v %#v", client, client, *client, *client), testSecret) {
		t.Error("client formatting exposed the secret")
	}
}

func TestDefaultAndConcurrentUse(t *testing.T) {
	data := loadFixtures(t)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body map[string]any
		json.NewDecoder(r.Body).Decode(&body)
		if body["challenge_type"] != "text" || body["rotation_source"] != nil || body["image_set_id"] != nil {
			t.Error("incorrect defaults")
		}
		json.NewEncoder(w).Encode(data.Session)
	}))
	defer server.Close()
	client := clientFor(t, server.URL)
	var workers sync.WaitGroup
	for i := 0; i < 8; i++ {
		workers.Add(1)
		go func() {
			defer workers.Done()
			_, err := client.CreateSession(context.Background(), SessionRequest{Action: "login", ContextID: data.Verification.ContextID, Origin: "https://app.example.com"})
			if err != nil {
				t.Error(err)
			}
		}()
	}
	workers.Wait()
}

func TestAPIErrorAndNoRetry(t *testing.T) {
	data := loadFixtures(t)
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		w.WriteHeader(429)
		json.NewEncoder(w).Encode(data.Failure)
	}))
	defer server.Close()
	_, err := clientFor(t, server.URL).SiteVerify(context.Background(), VerifyRequest{Token: "token.example", Action: "login", ContextID: data.Verification.ContextID})
	var failure *Error
	if !errors.As(err, &failure) || failure.Code != "RATE_LIMITED" || failure.StatusCode != 429 || failure.RequestID != "request_example" || failure.RetryAfter == nil || *failure.RetryAfter != 60 {
		t.Fatalf("incorrect error: %v", err)
	}
	if requests != 1 {
		t.Error("request was retried")
	}
}

func TestMalformedAndMismatchedResponses(t *testing.T) {
	data := loadFixtures(t)
	wrongSite, wrongAction, wrongContext, unsuccessful := data.Verification, data.Verification, data.Verification, data.Verification
	wrongSite.SiteKey = "other"
	wrongAction.Action = "register"
	wrongContext.ContextID = "context_other"
	unsuccessful.Success = false
	for _, reply := range []any{nil, []int{}, wrongSite, wrongAction, wrongContext, unsuccessful, "invalid JSON", strings.Repeat(" ", 65537)} {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if text, ok := reply.(string); ok {
				fmt.Fprint(w, text)
			} else {
				json.NewEncoder(w).Encode(reply)
			}
		}))
		_, err := clientFor(t, server.URL).SiteVerify(context.Background(), VerifyRequest{Token: "token.example", Action: "login", ContextID: data.Verification.ContextID})
		server.Close()
		var failure *Error
		if !errors.As(err, &failure) || failure.Code != "PROTOCOL_ERROR" {
			t.Fatalf("malformed reply accepted: %v", err)
		}
	}
}

func TestRedirectAndCancellation(t *testing.T) {
	for _, status := range []int{301, 302, 303, 307, 308} {
		requests := 0
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			requests++
			w.Header().Set("Location", "/unexpected")
			w.WriteHeader(status)
		}))
		_, err := clientFor(t, server.URL).CreateSession(context.Background(), SessionRequest{})
		server.Close()
		var failure *Error
		if !errors.As(err, &failure) || failure.Code != "REDIRECT_DENIED" || requests != 1 {
			t.Fatalf("redirect followed: %v", err)
		}
	}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		io.Copy(io.Discard, r.Body)
		select {
		case <-r.Context().Done():
		case <-time.After(100 * time.Millisecond):
		}
	}))
	defer server.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	_, err := clientFor(t, server.URL).CreateSession(ctx, SessionRequest{})
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("context deadline was lost: %v", err)
	}
}

func TestInvalidConfigAndSecretRedaction(t *testing.T) {
	for _, address := range []string{"", "file:///tmp/example", "http://[", "https://user:password@example.com", "https://example.com?key=x", "https://example.com/#fragment", "https://example.com?", "https://example.com#", "https://@example.com"} {
		if _, err := NewClient(Config{APIBase: address, SiteKey: "site_sdk_test", SiteSecret: testSecret}); err == nil {
			t.Error("invalid URL accepted")
		}
	}
	config := Config{APIBase: "https://example.com", SiteKey: "site_sdk_test", SiteSecret: testSecret}
	if strings.Contains(fmt.Sprintf("%+v %#v", config, config), testSecret) {
		t.Error("config formatting exposed the secret")
	}
}
