// Package login shows framework-independent business backend integration.
package login

import (
	"context"

	starlock "github.com/StarDreamTech/starlock/sdks/go"
)

// CreateChallenge receives the context saved by the business backend and its configured origin.
func CreateChallenge(ctx context.Context, client *starlock.Client, trustedContextID, allowedOrigin string) (*starlock.Session, error) {
	return client.CreateSession(ctx, starlock.SessionRequest{
		Action: "login", ContextID: trustedContextID, Origin: allowedOrigin, ChallengeType: starlock.SemanticGrid,
	})
}

// VerifyLogin receives the token from the browser and the context from the server-side session.
func VerifyLogin(ctx context.Context, client *starlock.Client, token, trustedContextID string) (*starlock.VerificationResult, error) {
	return client.SiteVerify(ctx, starlock.VerifyRequest{Token: token, Action: "login", ContextID: trustedContextID})
}
