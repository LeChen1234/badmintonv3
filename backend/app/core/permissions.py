from functools import wraps
from typing import List

from fastapi import HTTPException, status

from app.models.user import User, UserRole


def require_roles(allowed_roles: List[UserRole]):
    """Dependency factory that checks if the current user has one of the allowed roles."""
    def checker(current_user: User) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要角色: {[r.value for r in allowed_roles]}",
            )
        return current_user
    return checker


def is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


def is_expert(user: User) -> bool:
    return user.role == UserRole.EXPERT


def is_leader(user: User) -> bool:
    return user.role == UserRole.LEADER


def is_student(user: User) -> bool:
    return user.role == UserRole.STUDENT


def can_review_as_leader(user: User) -> bool:
    return user.role in (UserRole.ADMIN, UserRole.EXPERT, UserRole.LEADER)


def can_review_as_expert(user: User) -> bool:
    return user.role in (UserRole.ADMIN, UserRole.EXPERT)
