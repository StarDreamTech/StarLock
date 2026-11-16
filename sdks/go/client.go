// Package starlock connects a business backend to StarLock's session and verification API.
package starlock

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const maxResponseBytes = 65536

type ChallengeType string

const (
	Text         ChallengeType = "text"
	Digits       ChallengeType = "digits"
	Arithmetic   ChallengeType = "arithmetic"
	Slider       ChallengeType = "slider"
	BezierSlider ChallengeType = "bezier_slider"
	Rotate       ChallengeType = "rotate"
	TextClick    ChallengeType = "text_click"
	SemanticGrid ChallengeType = "semantic_grid"
)

type Config struct {
	APIBase    string
	SiteKey    string
	SiteSecret string
	HTTPClient *http.Client
}

func (c Config) String() string {
	return fmt.Sprintf("starlock.Config{APIBase:%q SiteKey:%q}", c.APIBase, c.SiteKey)
}
func (c Config) GoString() string { return c.String() }

// Client is safe for concurrent use. Its configuration is fixed at construction.
type Client struct {
	apiBase    string
	siteKey    string
	siteSecret string
	httpClient *http.Client
}

func (c Client) String() string {
	return fmt.Sprintf("starlock.Client{APIBase:%q SiteKey:%q}", c.apiBase, c.siteKey)
}
func (c Client) GoString() string { return c.String() }

type Error struct {
	Code       string `json:"error_code"`
	Message    string `json:"message"`
	StatusCode int    `json:"-"`
	RequestID  string `json:"request_id"`
	RetryAfter *int   `json:"retry_after,omitempty"`
	cause      error
}

func (e *Error) Error() string { return e.Code + ": " + e.Message }
func (e *Error) Unwrap() error { return e.cause }

type SessionRequest struct {
	Action         string        `json:"action"`
	ContextID      string        `json:"context_id"`
	Origin         string        `json:"origin"`
	ChallengeType  ChallengeType `json:"challenge_type"`
	RotationSource string        `json:"rotation_source,omitempty"`
	ImageSetID     string        `json:"image_set_id,omitempty"`
}

type Session struct {
	SiteKey       string `json:"site_key"`
	SessionTicket string `json:"session_ticket"`
	ExpiresIn     int    `json:"expires_in"`
}

type VerifyRequest struct {
	Token     string `json:"token"`
	Action    string `json:"action"`
	ContextID string `json:"context_id"`
}

type VerificationResult struct {
	Success       bool          `json:"success"`
	SiteKey       string        `json:"site_key"`
	Action        string        `json:"action"`
	ContextID     string        `json:"context_id"`
	Hostname      string        `json:"hostname"`
	ChallengeType ChallengeType `json:"challenge_type"`
	VerifiedAt    string        `json:"verified_at"`
}

func NewClient(config Config) (*Client, error) {
	address, err := url.Parse(config.APIBase)
	if err != nil || (address.Scheme != "https" && address.Scheme != "http") || address.Hostname() == "" ||
		address.User != nil || address.RawQuery != "" || address.Fragment != "" || strings.ContainsAny(config.APIBase, " ?#\t\r\n") {
		return nil, errors.New("api base must be an HTTP(S) URL without credentials, query or fragment")
	}
	if config.SiteKey == "" || config.SiteSecret == "" || strings.ContainsAny(config.SiteKey+config.SiteSecret, "\r\n") {
		return nil, errors.New("site key and secret must be nonempty single-line strings")
	}
	client := http.Client{Timeout: 10 * time.Second}
	if config.HTTPClient != nil {
		client = *config.HTTPClient
		if client.Timeout == 0 {
			client.Timeout = 10 * time.Second
		}
	}
	// Credentials must stay on the configured API endpoint, including same-host redirects.
	client.CheckRedirect = func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }
	return &Client{strings.TrimRight(config.APIBase, "/"), config.SiteKey, config.SiteSecret, &client}, nil
}

func (c *Client) post(ctx context.Context, path string, payload any, result any) error {
	encoded, err := json.Marshal(payload)
	if err != nil {
		return &Error{Code: "INVALID_REQUEST", Message: "Could not encode the StarLock request"}
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodPost, c.apiBase+path, bytes.NewReader(encoded))
	if err != nil {
		return &Error{Code: "INVALID_REQUEST", Message: "Could not create the StarLock request"}
	}
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("Accept", "application/json")
	request.Header.Set("User-Agent", "starlock-go/0.8.0")
	request.Header.Set("Authorization", "Bearer "+c.siteSecret)
	response, err := c.httpClient.Do(request)
	if err != nil {
		return &Error{Code: "NETWORK_ERROR", Message: "StarLock request failed; the operation outcome may be unknown", cause: err}
	}
	defer response.Body.Close()
	if response.StatusCode >= 300 && response.StatusCode < 400 {
		return &Error{Code: "REDIRECT_DENIED", Message: "StarLock API redirects are disabled", StatusCode: response.StatusCode}
	}
	raw, err := io.ReadAll(io.LimitReader(response.Body, maxResponseBytes+1))
	if err != nil {
		return &Error{Code: "NETWORK_ERROR", Message: "Could not read the StarLock response", cause: err}
	}
	if len(raw) > maxResponseBytes {
		return &Error{Code: "PROTOCOL_ERROR", Message: "StarLock response exceeded the size limit", StatusCode: response.StatusCode}
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		failure := &Error{StatusCode: response.StatusCode}
		if json.Unmarshal(raw, failure) != nil {
			return &Error{Code: "HTTP_ERROR", Message: "StarLock request was rejected", StatusCode: response.StatusCode}
		}
		if failure.Code == "" {
			failure.Code = "HTTP_ERROR"
		}
		if failure.Message == "" {
			failure.Message = "StarLock request was rejected"
		}
		return failure
	}
	if json.Unmarshal(raw, result) != nil {
		return &Error{Code: "PROTOCOL_ERROR", Message: "StarLock returned invalid JSON", StatusCode: response.StatusCode}
	}
	return nil
}

func (c *Client) CreateSession(ctx context.Context, request SessionRequest) (*Session, error) {
	if request.ChallengeType == "" {
		request.ChallengeType = Text
	}
	payload := struct {
		SiteKey string `json:"site_key"`
		SessionRequest
	}{c.siteKey, request}
	var result Session
	if err := c.post(ctx, "/v1/sessions", payload, &result); err != nil {
		return nil, err
	}
	if result.SiteKey != c.siteKey || result.SessionTicket == "" || result.ExpiresIn <= 0 {
		return nil, &Error{Code: "PROTOCOL_ERROR", Message: "StarLock returned an invalid session"}
	}
	return &result, nil
}

func (c *Client) SiteVerify(ctx context.Context, request VerifyRequest) (*VerificationResult, error) {
	payload := struct {
		SiteKey string `json:"site_key"`
		VerifyRequest
	}{c.siteKey, request}
	var result VerificationResult
	if err := c.post(ctx, "/v1/siteverify", payload, &result); err != nil {
		return nil, err
	}
	if !result.Success || result.SiteKey != c.siteKey || result.Action != request.Action || result.ContextID != request.ContextID ||
		result.Hostname == "" || result.ChallengeType == "" || result.VerifiedAt == "" {
		return nil, &Error{Code: "PROTOCOL_ERROR", Message: "StarLock returned an invalid verification result"}
	}
	return &result, nil
}
