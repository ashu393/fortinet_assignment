"""RBAC + tenant isolation helpers (placeholder)."""

ROLE_ADMIN = "admin"
ROLE_ANALYST = "analyst"
ROLE_VIEWER = "viewer"

def require_role(*roles: str):
    """FastAPI dependency placeholder."""
    raise NotImplementedError

def enforce_org_access(user_org_id: str, resource_org_id: str):
    """Raise 403 if mismatch."""
    if user_org_id != resource_org_id:
        raise PermissionError("Forbidden: cross-tenant access")
