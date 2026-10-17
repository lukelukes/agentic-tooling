package signup

// Test hooks exposing internals to the external test package.
var (
	NormalizeEmailForTest      = normalizeEmail
	BuildWelcomeMessageForTest = buildWelcomeMessage
)
