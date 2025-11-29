from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.database import get_db
from app.models.models import User, UserRole, PoliticalParty
from app.schemas.schemas import UserResponse, StandardResponse, PoliticalPartyCreate, PoliticalPartyResponse
from app.core.roles import get_current_admin, get_current_super_admin
from app.core.security import get_password_hash
from app.core.file_upload import FileUploadService

router = APIRouter()

# === ADMIN ENDPOINTS ===

@router.get("/users", response_model=StandardResponse[List[UserResponse]])
async def get_all_users(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get all users (Admin only)"""
    try:
        users = db.query(User).all()
        users_response = [UserResponse.model_validate(user) for user in users]
        
        return StandardResponse[List[UserResponse]](
            status=True,
            data=users_response,
            error=None,
            message=f"Retrieved {len(users_response)} users successfully"
        )
        
    except Exception as e:
        return StandardResponse[List[UserResponse]](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving users"
        )

@router.get("/users/{user_id}", response_model=StandardResponse[UserResponse])
async def get_user_by_id(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get specific user by ID (Admin only)"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return StandardResponse[UserResponse](
                status=False,
                data=None,
                error="User not found",
                message="User retrieval failed"
            )
        
        user_response = UserResponse.model_validate(user)
        
        return StandardResponse[UserResponse](
            status=True,
            data=user_response,
            error=None,
            message="User retrieved successfully"
        )
        
    except Exception as e:
        return StandardResponse[UserResponse](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving user"
        )

@router.put("/users/{user_id}/role", response_model=StandardResponse[UserResponse])
async def update_user_role(
    user_id: int,
    new_role: UserRole,
    current_user: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    """Update user role (Super Admin only)"""
    try:
        # Prevent self-role modification
        if user_id == current_user.id:
            return StandardResponse[UserResponse](
                status=False,
                data=None,
                error="Cannot modify your own role",
                message="Role update failed"
            )
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return StandardResponse[UserResponse](
                status=False,
                data=None,
                error="User not found",
                message="Role update failed"
            )
        
        # Update role
        user.role = new_role
        db.commit()
        db.refresh(user)
        
        user_response = UserResponse.model_validate(user)
        
        return StandardResponse[UserResponse](
            status=True,
            data=user_response,
            error=None,
            message=f"User role updated to {new_role.value}"
        )
        
    except Exception as e:
        db.rollback()
        return StandardResponse[UserResponse](
            status=False,
            data=None,
            error=str(e),
            message="Error updating user role"
        )

@router.put("/users/{user_id}/status", response_model=StandardResponse[UserResponse])
async def update_user_status(
    user_id: int,
    is_active: bool,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Activate/deactivate user (Admin only)"""
    try:
        # Prevent self-deactivation
        if user_id == current_user.id and not is_active:
            return StandardResponse[UserResponse](
                status=False,
                data=None,
                error="Cannot deactivate your own account",
                message="Status update failed"
            )
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return StandardResponse[UserResponse](
                status=False,
                data=None,
                error="User not found",
                message="Status update failed"
            )
        
        user.is_active = is_active
        db.commit()
        db.refresh(user)
        
        user_response = UserResponse.model_validate(user)
        status_text = "activated" if is_active else "deactivated"
        
        return StandardResponse[UserResponse](
            status=True,
            data=user_response,
            error=None,
            message=f"User {status_text} successfully"
        )
        
    except Exception as e:
        db.rollback()
        return StandardResponse[UserResponse](
            status=False,
            data=None,
            error=str(e),
            message="Error updating user status"
        )

@router.delete("/users/{user_id}", response_model=StandardResponse[dict])
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    """Delete user (Super Admin only)"""
    try:
        # Prevent self-deletion
        if user_id == current_user.id:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Cannot delete your own account",
                message="User deletion failed"
            )
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="User not found",
                message="User deletion failed"
            )
        
        db.delete(user)
        db.commit()
        
        return StandardResponse[dict](
            status=True,
            data={"deleted_user_id": user_id},
            error=None,
            message="User deleted successfully"
        )
        
    except Exception as e:
        db.rollback()
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error deleting user"
        )

# === POLITICAL PARTY MANAGEMENT ===

@router.post("/parties", response_model=StandardResponse[PoliticalPartyResponse])
async def create_political_party(
    name: str = Form(...),
    acronym: str = Form(...),
    description: Optional[str] = Form(None),
    founded_date: Optional[datetime] = Form(None),
    logo: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Create a new political party (Admin only)"""
    try:
        # Check if party with same name or acronym already exists
        existing_party = db.query(PoliticalParty).filter(
            (PoliticalParty.name == name) | (PoliticalParty.acronym == acronym)
        ).first()
        
        if existing_party:
            return StandardResponse[PoliticalPartyResponse](
                status=False,
                data=None,
                error="Political party with this name or acronym already exists",
                message="Party creation failed"
            )
        
        # Handle logo upload
        logo_url = None
        if logo:
            logo_url = await FileUploadService.save_upload_file(logo, "uploads/party_logos")
        
        # Create party
        party_data = {
            "name": name,
            "acronym": acronym,
            "description": description,
            "founded_date": founded_date,
            "logo_url": logo_url
        }
        
        party = PoliticalParty(**party_data)
        db.add(party)
        db.commit()
        db.refresh(party)
        
        party_response = PoliticalPartyResponse.model_validate(party)
        
        return StandardResponse[PoliticalPartyResponse](
            status=True,
            data=party_response,
            error=None,
            message="Political party created successfully"
        )
        
    except Exception as e:
        db.rollback()
        return StandardResponse[PoliticalPartyResponse](
            status=False,
            data=None,
            error=str(e),
            message="Error creating political party"
        )

@router.get("/parties", response_model=StandardResponse[List[PoliticalPartyResponse]])
async def get_all_parties(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get all political parties (Admin only)"""
    try:
        parties = db.query(PoliticalParty).all()
        parties_response = [PoliticalPartyResponse.model_validate(party) for party in parties]
        
        return StandardResponse[List[PoliticalPartyResponse]](
            status=True,
            data=parties_response,
            error=None,
            message=f"Retrieved {len(parties_response)} political parties"
        )
        
    except Exception as e:
        return StandardResponse[List[PoliticalPartyResponse]](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving political parties"
        )

# === USER PROFILE IMAGE MANAGEMENT ===

@router.put("/users/{user_id}/profile-image", response_model=StandardResponse[UserResponse])
async def update_user_profile_image(
    user_id: int,
    profile_image: UploadFile = File(...),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update user profile image (Admin only)"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return StandardResponse[UserResponse](
                status=False,
                data=None,
                error="User not found",
                message="Profile image update failed"
            )
        
        # Delete old profile image if exists
        if user.profile_image_url:
            FileUploadService.delete_file(user.profile_image_url)
        
        # Save new profile image
        profile_image_url = await FileUploadService.save_upload_file(profile_image, "uploads/profile_images")
        user.profile_image_url = profile_image_url
        
        db.commit()
        db.refresh(user)
        
        user_response = UserResponse.model_validate(user)
        
        return StandardResponse[UserResponse](
            status=True,
            data=user_response,
            error=None,
            message="Profile image updated successfully"
        )
        
    except Exception as e:
        db.rollback()
        return StandardResponse[UserResponse](
            status=False,
            data=None,
            error=str(e),
            message="Error updating profile image"
        )

# === CANDIDATE IMAGE MANAGEMENT ===

@router.put("/candidates/{candidate_id}/profile-image", response_model=StandardResponse[dict])
async def update_candidate_profile_image(
    candidate_id: int,
    profile_image: UploadFile = File(...),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update candidate profile image (Admin only)"""
    try:
        from app.models.models import Candidate
        
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Candidate not found",
                message="Profile image update failed"
            )
        
        # Delete old profile image if exists
        if candidate.profile_image_url:
            FileUploadService.delete_file(candidate.profile_image_url)
        
        # Save new profile image
        profile_image_url = await FileUploadService.save_upload_file(profile_image, "uploads/candidate_images")
        candidate.profile_image_url = profile_image_url
        
        db.commit()
        
        return StandardResponse[dict](
            status=True,
            data={"candidate_id": candidate_id, "profile_image_url": profile_image_url},
            error=None,
            message="Candidate profile image updated successfully"
        )
        
    except Exception as e:
        db.rollback()
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error updating candidate profile image"
        )

# === ADMIN DASHBOARD ENDPOINTS ===

@router.get("/dashboard/stats", response_model=StandardResponse[dict])
async def get_dashboard_stats(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get admin dashboard statistics"""
    try:
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        admin_users = db.query(User).filter(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN])).count()
        
        stats = {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": total_users - active_users,
            "admin_users": admin_users,
            "regular_users": total_users - admin_users
        }
        
        return StandardResponse[dict](
            status=True,
            data=stats,
            error=None,
            message="Dashboard stats retrieved successfully"
        )
        
    except Exception as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving dashboard stats"
        )