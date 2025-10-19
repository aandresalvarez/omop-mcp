"""
OAuth 2.1 authentication and authorization middleware for OMOP MCP server.

Provides JWT token validation, role-based access control, and audit logging.
"""

from typing import Any

import jwt
import structlog
from jwt import PyJWKClient

from omop_mcp.config import config

logger = structlog.get_logger(__name__)


class AuthenticationError(Exception):
    """Raised when authentication fails."""

    pass


class AuthorizationError(Exception):
    """Raised when user lacks required permissions."""

    pass


class OAuthValidator:
    """
    OAuth 2.1 token validator with JWT verification.

    Validates bearer tokens against configured issuer and audience,
    checks expiration, and extracts user claims for authorization.
    """

    def __init__(
        self,
        issuer: str | None = None,
        audience: str | None = None,
        jwks_uri: str | None = None,
    ):
        """
        Initialize OAuth validator.

        Args:
            issuer: Expected JWT issuer (e.g., "https://auth.example.com")
                   Pass None explicitly to disable OAuth
            audience: Expected JWT audience (e.g., "omop-mcp-api")
                     Pass None explicitly to disable OAuth
            jwks_uri: JWKS endpoint for public key fetching
                     (default: {issuer}/.well-known/jwks.json)
        """
        # Allow explicit None to disable OAuth even if config has values
        if issuer is None and audience is None:
            self.issuer = None
            self.audience = None
            self.enabled = False
            self.jwks_client = None
            logger.warning(
                "oauth_disabled",
                message="OAuth explicitly disabled (issuer and audience are None)",
            )
        else:
            # Use provided values or fall back to config
            self.issuer = issuer if issuer is not None else config.oauth_issuer
            self.audience = audience if audience is not None else config.oauth_audience

            if not self.issuer or not self.audience:
                logger.warning(
                    "oauth_not_configured",
                    message="OAuth issuer/audience not set. Authentication disabled.",
                )
                self.enabled = False
                self.jwks_client = None
            else:
                self.enabled = True
                # JWKS client for fetching public keys
                self.jwks_uri = jwks_uri or f"{self.issuer}/.well-known/jwks.json"
                self.jwks_client = PyJWKClient(self.jwks_uri)
                logger.info(
                    "oauth_configured",
                    issuer=self.issuer,
                    audience=self.audience,
                    jwks_uri=self.jwks_uri,
                )

    def validate_token(self, token: str) -> dict[str, Any]:
        """
        Validate JWT bearer token.

        Args:
            token: JWT token string (without "Bearer " prefix)

        Returns:
            Decoded JWT payload with claims

        Raises:
            AuthenticationError: If token invalid, expired, or malformed
        """
        if not self.enabled:
            # OAuth disabled - return anonymous user
            logger.debug("oauth_disabled", message="Skipping token validation")
            return {"sub": "anonymous", "roles": []}

        try:
            # Get signing key from JWKS
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)

            # Decode and validate JWT
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],  # OAuth 2.1 requires asymmetric signing
                issuer=self.issuer,
                audience=self.audience,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )

            # Extract user claims
            user_id = payload.get("sub", "unknown")
            roles = payload.get("roles", [])
            scopes = payload.get("scope", "").split()

            logger.info(
                "token_validated",
                user_id=user_id,
                roles=roles,
                scopes=scopes,
                expires_at=payload.get("exp"),
            )

            return dict(payload)  # Ensure return type is dict[str, Any]

        except jwt.ExpiredSignatureError as e:
            logger.warning("token_expired", error=str(e))
            raise AuthenticationError("Token has expired") from e

        except jwt.InvalidAudienceError as e:
            logger.warning(
                "invalid_audience",
                error=str(e),
                expected=self.audience,
                token_aud=getattr(e, "audience", None),
            )
            raise AuthenticationError(f"Token audience mismatch. Expected: {self.audience}") from e

        except jwt.InvalidIssuerError as e:
            logger.warning(
                "invalid_issuer",
                error=str(e),
                expected=self.issuer,
                token_iss=getattr(e, "issuer", None),
            )
            raise AuthenticationError(f"Token issuer mismatch. Expected: {self.issuer}") from e

        except jwt.InvalidTokenError as e:
            logger.error("invalid_token", error=str(e), exc_info=True)
            raise AuthenticationError(f"Invalid token: {str(e)}") from e

        except Exception as e:
            logger.error("token_validation_failed", error=str(e), exc_info=True)
            raise AuthenticationError(f"Token validation failed: {str(e)}") from e

    def check_permission(self, token_payload: dict[str, Any], required_role: str) -> bool:
        """
        Check if user has required role.

        Args:
            token_payload: Decoded JWT payload from validate_token()
            required_role: Role required for operation (e.g., "admin", "researcher")

        Returns:
            True if user has role, False otherwise
        """
        if not self.enabled:
            # OAuth disabled - allow all
            return True

        roles = token_payload.get("roles", [])

        # Admin role bypasses all checks
        if "admin" in roles:
            return True

        # Check specific role
        has_permission = required_role in roles

        logger.debug(
            "permission_check",
            user_id=token_payload.get("sub"),
            required_role=required_role,
            user_roles=roles,
            granted=has_permission,
        )

        return has_permission

    def require_permission(self, token_payload: dict[str, Any], required_role: str) -> None:
        """
        Require user to have specific role, raise exception if not.

        Args:
            token_payload: Decoded JWT payload
            required_role: Required role

        Raises:
            AuthorizationError: If user lacks permission
        """
        if not self.check_permission(token_payload, required_role):
            user_id = token_payload.get("sub", "unknown")
            logger.warning(
                "permission_denied",
                user_id=user_id,
                required_role=required_role,
                user_roles=token_payload.get("roles", []),
            )
            raise AuthorizationError(f"User {user_id} lacks required role: {required_role}")

    def extract_user_id(self, token_payload: dict[str, Any]) -> str:
        """
        Extract user ID from token payload.

        Args:
            token_payload: Decoded JWT payload

        Returns:
            User ID (subject claim)
        """
        return str(token_payload.get("sub", "anonymous"))


def parse_bearer_token(authorization_header: str) -> str:
    """
    Extract JWT token from Authorization header.

    Args:
        authorization_header: Full Authorization header value

    Returns:
        JWT token string (without "Bearer " prefix)

    Raises:
        AuthenticationError: If header malformed
    """
    if not authorization_header:
        raise AuthenticationError("Missing Authorization header")

    parts = authorization_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationError("Invalid Authorization header. Expected: 'Bearer <token>'")

    return parts[1]


# Global validator instance
_validator: OAuthValidator | None = None


def get_validator() -> OAuthValidator:
    """
    Get global OAuth validator instance (singleton).

    Returns:
        Configured OAuthValidator
    """
    global _validator
    if _validator is None:
        _validator = OAuthValidator()
    return _validator


def validate_request_token(authorization_header: str) -> dict[str, Any]:
    """
    Convenience function: parse and validate token from request header.

    Args:
        authorization_header: Authorization header from HTTP request

    Returns:
        Decoded JWT payload

    Raises:
        AuthenticationError: If token invalid or missing
    """
    token = parse_bearer_token(authorization_header)
    validator = get_validator()
    return validator.validate_token(token)
