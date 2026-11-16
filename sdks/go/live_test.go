package starlock

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"os"
	"testing"
)

// This test uses only the isolated test API started by the backend test suite.
func TestLiveAPI(t *testing.T) {
	base := os.Getenv("STARLOCK_TEST_API_BASE")
	if base == "" {
		t.Skip("isolated backend integration API is not running")
	}
	client, err := NewClient(Config{APIBase: base, SiteKey: os.Getenv("STARLOCK_TEST_SITE_KEY"), SiteSecret: os.Getenv("STARLOCK_TEST_SITE_SECRET")})
	if err != nil {
		t.Fatal(err)
	}
	ctx := context.Background()
	for _, kind := range []ChallengeType{Text, Digits, Arithmetic, Slider, BezierSlider, Rotate, TextClick, SemanticGrid} {
		if _, err := client.CreateSession(ctx, SessionRequest{Action: "login", ContextID: "context_go_types_123", Origin: "https://app.example.com", ChallengeType: kind}); err != nil {
			t.Fatalf("%s session failed: %v", kind, err)
		}
	}
	session, err := client.CreateSession(ctx, SessionRequest{Action: "login", ContextID: "context_go_flow_123", Origin: "https://app.example.com"})
	if err != nil {
		t.Fatal(err)
	}
	browserPost := func(path string, answer string) map[string]any {
		body := map[string]any{"site_key": session.SiteKey, "session_ticket": session.SessionTicket}
		if answer != "" {
			body["answer"] = answer
		}
		raw, _ := json.Marshal(body)
		request, _ := http.NewRequest(http.MethodPost, base+path, bytes.NewReader(raw))
		request.Header.Set("Content-Type", "application/json")
		request.Header.Set("Origin", "https://app.example.com")
		response, err := http.DefaultClient.Do(request)
		if err != nil {
			t.Fatal(err)
		}
		defer response.Body.Close()
		var result map[string]any
		if err := json.NewDecoder(response.Body).Decode(&result); err != nil || response.StatusCode != 200 {
			t.Fatalf("test browser step failed, status %d", response.StatusCode)
		}
		return result
	}
	challenge := browserPost("/v1/challenges", "")
	token := browserPost("/v1/challenges/"+challenge["challenge_id"].(string)+"/verify", "ABCDE")["verification_token"].(string)
	wrong := VerifyRequest{Token: token, Action: "login", ContextID: "context_wrong_123"}
	_, err = client.SiteVerify(ctx, wrong)
	var failure *Error
	if !errors.As(err, &failure) || failure.Code != "CONTEXT_MISMATCH" {
		t.Fatalf("wrong context accepted: %v", err)
	}
	request := VerifyRequest{Token: token, Action: "login", ContextID: "context_go_flow_123"}
	result, err := client.SiteVerify(ctx, request)
	if err != nil || !result.Success {
		t.Fatalf("live verification failed: %v", err)
	}
	_, err = client.SiteVerify(ctx, request)
	if !errors.As(err, &failure) || failure.Code != "TOKEN_USED" {
		t.Fatalf("replayed token accepted: %v", err)
	}
}
