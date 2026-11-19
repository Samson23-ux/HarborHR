from datetime import datetime

from app.api.models.user import User
from app.api.schemas.user import CachedUser


def _serialize_user(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email or "",
        "role": str(user.role.name),
        "employee_id": str(user.employee_id) if user.employee_id else "",
        "organization_id": str(user.organization_id) if user.organization_id else "",
        "hashed_password": user.hashed_password or "",
        "google_id": user.google_id or "",
        "google_email": user.google_email or "",
        "is_active": "1" if user.is_active else "0",
        "is_verified": "1" if user.is_verified else "0",
        "updated_at": user.updated_at.isoformat() if user.updated_at else "",
        "created_at": user.created_at.isoformat(),
    }


def _deserialize_cached_user(cached: dict) -> CachedUser:
    return CachedUser(
        id=cached["id"],
        email=cached["email"] or None,
        role=cached["role"],
        employee_id=cached["employee_id"] or None,
        organization_id=cached["organization_id"] or None,
        hashed_password=cached["hashed_password"] or None,
        google_id=cached["google_id"] or None,
        google_email=cached["google_email"] or None,
        is_active=bool(cached["is_active"]),
        is_verified=bool(cached["is_verified"]),
        updated_at=datetime.fromisoformat(cached["updated_at"])
        if cached["updated_at"]
        else None,
        created_at=datetime.fromisoformat(cached["created_at"]),
    )
