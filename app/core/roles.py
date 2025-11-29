from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.models.models import User, UserRole
from app.routes.auth import get_current_user
from app.models.database import get_db

# Role-based dependency injections
async def get_current_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """Verify current user has admin or super_admin role"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Admin access required."
        )
    return current_user

async def get_current_super_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """Verify current user has super_admin role"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Super Admin access required."
        )
    return current_user

# Role checking utilities
def has_admin_role(user: User) -> bool:
    return user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]

def has_super_admin_role(user: User) -> bool:
    return user.role == UserRole.SUPER_ADMIN