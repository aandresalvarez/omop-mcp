"""
Tests for OAuth 2.1 authentication and authorization.
"""

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from omop_mcp.auth import (
    AuthenticationError,
    AuthorizationError,
    OAuthValidator,
    get_validator,
    parse_bearer_token,
    validate_request_token,
)


class TestParseBearerToken:
    """Tests for bearer token parsing."""

    def test_valid_bearer_token(self):
        """Parse valid Authorization header."""
        header = "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test.token"
        token = parse_bearer_token(header)
        assert token == "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test.token"

    def test_missing_authorization_header(self):
        """Reject missing Authorization header."""
        with pytest.raises(AuthenticationError, match="Missing Authorization header"):
            parse_bearer_token("")

    def test_malformed_authorization_header(self):
        """Reject malformed Authorization header."""
        with pytest.raises(AuthenticationError, match="Invalid Authorization header"):
            parse_bearer_token("InvalidFormat token")

    def test_missing_token_value(self):
        """Reject Authorization header without token."""
        with pytest.raises(AuthenticationError, match="Invalid Authorization header"):
            parse_bearer_token("Bearer")

    def test_case_insensitive_bearer(self):
        """Accept case-insensitive 'Bearer' keyword."""
        header = "bearer test.token.here"
        token = parse_bearer_token(header)
        assert token == "test.token.here"


class TestOAuthValidator:
    """Tests for OAuth validator."""

    def test_validator_disabled_when_not_configured(self):
        """Validator is disabled when issuer/audience not set."""
        validator = OAuthValidator(issuer=None, audience=None)
        assert validator.enabled is False

    def test_validator_enabled_when_configured(self):
        """Validator is enabled when issuer/audience set."""
        validator = OAuthValidator(issuer="https://auth.example.com", audience="omop-mcp-api")
        assert validator.enabled is True
        assert validator.issuer == "https://auth.example.com"
        assert validator.audience == "omop-mcp-api"

    def test_validate_token_returns_anonymous_when_disabled(self):
        """Return anonymous user when OAuth disabled."""
        validator = OAuthValidator(issuer=None, audience=None)
        payload = validator.validate_token("any-token")

        assert payload["sub"] == "anonymous"
        assert payload["roles"] == []

    @patch("omop_mcp.auth.PyJWKClient")
    def test_validate_token_success(self, mock_jwks_client_class):
        """Successfully validate valid JWT."""
        # Mock JWKS client
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-public-key"

        mock_jwks_client = MagicMock()
        mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_jwks_client_class.return_value = mock_jwks_client

        validator = OAuthValidator(issuer="https://auth.example.com", audience="omop-mcp-api")

        # Mock JWT decode
        expected_payload = {
            "sub": "user123",
            "roles": ["researcher"],
            "scope": "read write",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "aud": "omop-mcp-api",
            "iss": "https://auth.example.com",
        }

        with patch("omop_mcp.auth.jwt.decode") as mock_decode:
            mock_decode.return_value = expected_payload

            payload = validator.validate_token("valid.jwt.token")

            assert payload["sub"] == "user123"
            assert payload["roles"] == ["researcher"]
            assert "read" in payload["scope"]

    @patch("omop_mcp.auth.PyJWKClient")
    def test_validate_token_expired(self, mock_jwks_client_class):
        """Reject expired JWT."""
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-public-key"

        mock_jwks_client = MagicMock()
        mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_jwks_client_class.return_value = mock_jwks_client

        validator = OAuthValidator(issuer="https://auth.example.com", audience="omop-mcp-api")

        with patch("omop_mcp.auth.jwt.decode") as mock_decode:
            mock_decode.side_effect = jwt.ExpiredSignatureError("Token expired")

            with pytest.raises(AuthenticationError, match="Token has expired"):
                validator.validate_token("expired.jwt.token")

    @patch("omop_mcp.auth.PyJWKClient")
    def test_validate_token_invalid_audience(self, mock_jwks_client_class):
        """Reject JWT with wrong audience."""
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-public-key"

        mock_jwks_client = MagicMock()
        mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_jwks_client_class.return_value = mock_jwks_client

        validator = OAuthValidator(issuer="https://auth.example.com", audience="omop-mcp-api")

        with patch("omop_mcp.auth.jwt.decode") as mock_decode:
            mock_decode.side_effect = jwt.InvalidAudienceError("Wrong audience")

            with pytest.raises(AuthenticationError, match="audience mismatch"):
                validator.validate_token("wrong.audience.token")

    @patch("omop_mcp.auth.PyJWKClient")
    def test_validate_token_invalid_issuer(self, mock_jwks_client_class):
        """Reject JWT with wrong issuer."""
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-public-key"

        mock_jwks_client = MagicMock()
        mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_jwks_client_class.return_value = mock_jwks_client

        validator = OAuthValidator(issuer="https://auth.example.com", audience="omop-mcp-api")

        with patch("omop_mcp.auth.jwt.decode") as mock_decode:
            mock_decode.side_effect = jwt.InvalidIssuerError("Wrong issuer")

            with pytest.raises(AuthenticationError, match="issuer mismatch"):
                validator.validate_token("wrong.issuer.token")

    def test_check_permission_with_required_role(self):
        """Check user has required role."""
        validator = OAuthValidator(issuer="https://auth.example.com", audience="omop-mcp-api")

        payload = {"sub": "user123", "roles": ["researcher", "data-analyst"]}

        assert validator.check_permission(payload, "researcher") is True
        assert validator.check_permission(payload, "data-analyst") is True
        assert validator.check_permission(payload, "admin") is False

    def test_check_permission_admin_bypass(self):
        """Admin role bypasses all permission checks."""
        validator = OAuthValidator(issuer="https://auth.example.com", audience="omop-mcp-api")

        payload = {"sub": "admin-user", "roles": ["admin"]}

        assert validator.check_permission(payload, "any-role") is True
        assert validator.check_permission(payload, "researcher") is True

    def test_check_permission_when_disabled(self):
        """Allow all permissions when OAuth disabled."""
        validator = OAuthValidator(issuer=None, audience=None)

        payload = {"sub": "anonymous", "roles": []}

        assert validator.check_permission(payload, "admin") is True

    def test_require_permission_success(self):
        """Require permission succeeds when user has role."""
        validator = OAuthValidator(issuer="https://auth.example.com", audience="omop-mcp-api")

        payload = {"sub": "user123", "roles": ["researcher"]}

        # Should not raise
        validator.require_permission(payload, "researcher")

    def test_require_permission_failure(self):
        """Require permission fails when user lacks role."""
        validator = OAuthValidator(issuer="https://auth.example.com", audience="omop-mcp-api")

        payload = {"sub": "user123", "roles": ["data-analyst"]}

        with pytest.raises(AuthorizationError, match="lacks required role"):
            validator.require_permission(payload, "admin")

    def test_extract_user_id(self):
        """Extract user ID from token payload."""
        validator = OAuthValidator(issuer="https://auth.example.com", audience="omop-mcp-api")

        payload = {"sub": "user123", "roles": ["researcher"]}

        user_id = validator.extract_user_id(payload)
        assert user_id == "user123"

    def test_extract_user_id_default(self):
        """Return 'anonymous' if subject missing."""
        validator = OAuthValidator(issuer="https://auth.example.com", audience="omop-mcp-api")

        payload = {"roles": ["researcher"]}

        user_id = validator.extract_user_id(payload)
        assert user_id == "anonymous"


class TestGlobalValidator:
    """Tests for global validator singleton."""

    def test_get_validator_returns_singleton(self):
        """get_validator returns same instance."""
        validator1 = get_validator()
        validator2 = get_validator()

        assert validator1 is validator2

    @patch("omop_mcp.auth.PyJWKClient")
    def test_validate_request_token(self, mock_jwks_client_class):
        """Validate token from Authorization header."""
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"

        mock_jwks_client = MagicMock()
        mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_jwks_client_class.return_value = mock_jwks_client

        expected_payload = {
            "sub": "user123",
            "roles": ["researcher"],
            "exp": int(time.time()) + 3600,
        }

        with patch("omop_mcp.auth.jwt.decode") as mock_decode:
            mock_decode.return_value = expected_payload

            # Clear global validator to test with OAuth enabled
            import omop_mcp.auth

            omop_mcp.auth._validator = OAuthValidator(
                issuer="https://auth.example.com", audience="omop-mcp-api"
            )

            payload = validate_request_token("Bearer valid.jwt.token")

            assert payload["sub"] == "user123"
            assert payload["roles"] == ["researcher"]


class TestAuthenticationScenarios:
    """Integration tests for authentication scenarios."""

    def test_disabled_oauth_allows_anonymous_access(self):
        """When OAuth disabled, allow anonymous access."""
        validator = OAuthValidator(issuer=None, audience=None)

        # Any token works
        payload = validator.validate_token("any-token-here")
        assert payload["sub"] == "anonymous"

        # All permissions granted
        assert validator.check_permission(payload, "admin") is True

    @patch("omop_mcp.auth.PyJWKClient")
    def test_valid_token_grants_access(self, mock_jwks_client_class):
        """Valid token with correct roles grants access."""
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"

        mock_jwks_client = MagicMock()
        mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_jwks_client_class.return_value = mock_jwks_client

        validator = OAuthValidator(issuer="https://auth.example.com", audience="omop-mcp-api")

        payload = {
            "sub": "researcher123",
            "roles": ["researcher"],
            "exp": int(time.time()) + 3600,
        }

        with patch("omop_mcp.auth.jwt.decode") as mock_decode:
            mock_decode.return_value = payload

            # Validate token
            validated = validator.validate_token("valid.token")
            assert validated["sub"] == "researcher123"

            # Check permissions
            assert validator.check_permission(validated, "researcher") is True
            assert validator.check_permission(validated, "admin") is False

    @patch("omop_mcp.auth.PyJWKClient")
    def test_expired_token_denies_access(self, mock_jwks_client_class):
        """Expired token is rejected."""
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"

        mock_jwks_client = MagicMock()
        mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_jwks_client_class.return_value = mock_jwks_client

        validator = OAuthValidator(issuer="https://auth.example.com", audience="omop-mcp-api")

        with patch("omop_mcp.auth.jwt.decode") as mock_decode:
            mock_decode.side_effect = jwt.ExpiredSignatureError()

            with pytest.raises(AuthenticationError):
                validator.validate_token("expired.token")
