from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.database import get_db
from app.models.models import User, UserRole, PoliticalParty, Candidate, Election
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

@router.put("/users/{user_id}", response_model=StandardResponse[UserResponse], summary="Update User Profile")
async def update_user_profile(
    user_id: int,
    full_name: Optional[str] = Form(None, description="User's full name"),
    email: Optional[str] = Form(None, description="User's email address"),
    state_of_residence: Optional[str] = Form(None, description="State of residence"),
    date_of_birth: Optional[str] = Form(None, description="Date of birth (YYYY-MM-DD or ISO format)"),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Update user profile information.
    
    **Admin only** - Requires admin authentication.
    
    All fields are optional. Only provided fields will be updated.
    
    - **full_name**: User's full name
    - **email**: User's email address (must be unique)
    - **state_of_residence**: State where user resides
    - **date_of_birth**: Date of birth in format YYYY-MM-DD or ISO format
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return StandardResponse[UserResponse](
                status=False,
                data=None,
                error="User not found",
                message="User update failed"
            )
        
        # Update fields if provided
        if full_name:
            user.full_name = full_name
        if email:
            # Check if email already exists for another user
            existing_user = db.query(User).filter(User.email == email, User.id != user_id).first()
            if existing_user:
                return StandardResponse[UserResponse](
                    status=False,
                    data=None,
                    error="Email already exists",
                    message="User update failed"
                )
            user.email = email
        if state_of_residence:
            user.state_of_residence = state_of_residence
        if date_of_birth:
            # Parse the date string
            try:
                # Try different date formats
                for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%SZ"]:
                    try:
                        parsed_date = datetime.strptime(date_of_birth, fmt)
                        user.date_of_birth = parsed_date
                        break
                    except ValueError:
                        continue
                else:
                    # If no format matched, try fromisoformat
                    user.date_of_birth = datetime.fromisoformat(date_of_birth.replace('Z', '+00:00'))
            except Exception as date_error:
                return StandardResponse[UserResponse](
                    status=False,
                    data=None,
                    error=f"Invalid date format. Use YYYY-MM-DD or ISO format. Error: {str(date_error)}",
                    message="User update failed"
                )
        
        db.commit()
        db.refresh(user)
        
        user_response = UserResponse.model_validate(user)
        
        return StandardResponse[UserResponse](
            status=True,
            data=user_response,
            error=None,
            message="User profile updated successfully"
        )
        
    except Exception as e:
        db.rollback()
        return StandardResponse[UserResponse](
            status=False,
            data=None,
            error=str(e),
            message="Error updating user profile"
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

@router.put("/parties/{party_id}", response_model=StandardResponse[PoliticalPartyResponse])
async def update_political_party(
    party_id: int,
    name: Optional[str] = Form(None),
    acronym: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    founded_date: Optional[datetime] = Form(None),
    logo: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update political party (Admin only)"""
    try:
        party = db.query(PoliticalParty).filter(PoliticalParty.id == party_id).first()
        if not party:
            return StandardResponse[PoliticalPartyResponse](
                status=False,
                data=None,
                error="Political party not found",
                message="Party update failed"
            )
        
        # Check if new name or acronym conflicts with existing parties
        if name and name != party.name:
            existing = db.query(PoliticalParty).filter(
                PoliticalParty.name == name, 
                PoliticalParty.id != party_id
            ).first()
            if existing:
                return StandardResponse[PoliticalPartyResponse](
                    status=False,
                    data=None,
                    error="Party name already exists",
                    message="Party update failed"
                )
            party.name = name
        
        if acronym and acronym != party.acronym:
            existing = db.query(PoliticalParty).filter(
                PoliticalParty.acronym == acronym,
                PoliticalParty.id != party_id
            ).first()
            if existing:
                return StandardResponse[PoliticalPartyResponse](
                    status=False,
                    data=None,
                    error="Party acronym already exists",
                    message="Party update failed"
                )
            party.acronym = acronym
        
        if description is not None:
            party.description = description
        if founded_date:
            party.founded_date = founded_date
        
        # Handle logo upload
        if logo:
            # Delete old logo if exists
            if party.logo_url:
                FileUploadService.delete_file(party.logo_url)
            party.logo_url = await FileUploadService.save_upload_file(logo, "uploads/party_logos")
        
        db.commit()
        db.refresh(party)
        
        party_response = PoliticalPartyResponse.model_validate(party)
        
        return StandardResponse[PoliticalPartyResponse](
            status=True,
            data=party_response,
            error=None,
            message="Political party updated successfully"
        )
        
    except Exception as e:
        db.rollback()
        return StandardResponse[PoliticalPartyResponse](
            status=False,
            data=None,
            error=str(e),
            message="Error updating political party"
        )

@router.delete("/parties/{party_id}", response_model=StandardResponse[dict])
async def delete_political_party(
    party_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Delete political party (Admin only)"""
    try:
        party = db.query(PoliticalParty).filter(PoliticalParty.id == party_id).first()
        if not party:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Political party not found",
                message="Party deletion failed"
            )
        
        # Check if party has candidates
        candidates = db.query(Candidate).filter(Candidate.party_id == party_id).count()
        if candidates > 0:
            return StandardResponse[dict](
                status=False,
                data=None,
                error=f"Cannot delete party with {candidates} associated candidates",
                message="Party deletion failed"
            )
        
        # Delete logo if exists
        if party.logo_url:
            FileUploadService.delete_file(party.logo_url)
        
        db.delete(party)
        db.commit()
        
        return StandardResponse[dict](
            status=True,
            data={"deleted_party_id": party_id},
            error=None,
            message="Political party deleted successfully"
        )
        
    except Exception as e:
        db.rollback()
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error deleting political party"
        )

# === CANDIDATE MANAGEMENT ===

@router.put("/candidates/{candidate_id}", response_model=StandardResponse[dict])
async def update_candidate(
    candidate_id: int,
    name: Optional[str] = Form(None),
    bio: Optional[str] = Form(None),
    party_id: Optional[int] = Form(None),
    position_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update candidate (Admin only)"""
    try:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Candidate not found",
                message="Candidate update failed"
            )
        
        # Update fields if provided
        if name:
            candidate.name = name
        if bio is not None:
            candidate.bio = bio
        if party_id:
            # Verify party exists
            party = db.query(PoliticalParty).filter(PoliticalParty.id == party_id).first()
            if not party:
                return StandardResponse[dict](
                    status=False,
                    data=None,
                    error="Political party not found",
                    message="Candidate update failed"
                )
            candidate.party_id = party_id
        if position_id:
            # Verify position exists
            from app.models.models import Position
            position = db.query(Position).filter(Position.id == position_id).first()
            if not position:
                return StandardResponse[dict](
                    status=False,
                    data=None,
                    error="Position not found",
                    message="Candidate update failed"
                )
            candidate.position_id = position_id
        
        db.commit()
        db.refresh(candidate)
        
        return StandardResponse[dict](
            status=True,
            data={
                "candidate_id": candidate.id,
                "name": candidate.name,
                "bio": candidate.bio,
                "party_id": candidate.party_id,
                "position_id": candidate.position_id
            },
            error=None,
            message="Candidate updated successfully"
        )
        
    except Exception as e:
        db.rollback()
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error updating candidate"
        )

@router.delete("/candidates/{candidate_id}", response_model=StandardResponse[dict])
async def delete_candidate(
    candidate_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Delete candidate (Admin only)"""
    try:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Candidate not found",
                message="Candidate deletion failed"
            )
        
        # Check if candidate has votes
        from app.models.models import Vote
        votes = db.query(Vote).filter(Vote.candidate_id == candidate_id).count()
        if votes > 0:
            return StandardResponse[dict](
                status=False,
                data=None,
                error=f"Cannot delete candidate with {votes} votes",
                message="Candidate deletion failed"
            )
        
        # Delete profile image if exists
        if candidate.profile_image_url:
            FileUploadService.delete_file(candidate.profile_image_url)
        
        db.delete(candidate)
        db.commit()
        
        return StandardResponse[dict](
            status=True,
            data={"deleted_candidate_id": candidate_id},
            error=None,
            message="Candidate deleted successfully"
        )
        
    except Exception as e:
        db.rollback()
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error deleting candidate"
        )

# === ELECTION MANAGEMENT ===

@router.put("/elections/{election_id}", response_model=StandardResponse[dict])
async def update_election(
    election_id: int,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    election_type: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(None),
    start_date: Optional[datetime] = Form(None),
    end_date: Optional[datetime] = Form(None),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update election (Admin only)"""
    try:
        election = db.query(Election).filter(Election.id == election_id).first()
        if not election:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Election not found",
                message="Election update failed"
            )
        
        # Update fields if provided
        if title:
            election.title = title
        if description is not None:
            election.description = description
        if election_type:
            election.election_type = election_type
        if state is not None:
            election.state = state
        if is_active is not None:
            election.is_active = is_active
        if start_date:
            election.start_date = start_date
        if end_date:
            election.end_date = end_date
        
        # Validate dates
        if election.start_date and election.end_date and election.start_date >= election.end_date:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="End date must be after start date",
                message="Election update failed"
            )
        
        db.commit()
        db.refresh(election)
        
        return StandardResponse[dict](
            status=True,
            data={
                "election_id": election.id,
                "title": election.title,
                "description": election.description,
                "election_type": election.election_type,
                "state": election.state,
                "is_active": election.is_active,
                "start_date": str(election.start_date) if election.start_date else None,
                "end_date": str(election.end_date) if election.end_date else None
            },
            error=None,
            message="Election updated successfully"
        )
        
    except Exception as e:
        db.rollback()
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error updating election"
        )

@router.delete("/elections/{election_id}", response_model=StandardResponse[dict])
async def delete_election(
    election_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Delete election (Admin only)"""
    try:
        election = db.query(Election).filter(Election.id == election_id).first()
        if not election:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Election not found",
                message="Election deletion failed"
            )
        
        # Check if election has votes
        from app.models.models import Vote
        votes = db.query(Vote).filter(Vote.election_id == election_id).count()
        if votes > 0:
            return StandardResponse[dict](
                status=False,
                data=None,
                error=f"Cannot delete election with {votes} votes",
                message="Election deletion failed"
            )
        
        # Delete associated positions and candidates
        from app.models.models import Position
        positions = db.query(Position).filter(Position.election_id == election_id).all()
        for position in positions:
            # Delete candidates for this position
            candidates = db.query(Candidate).filter(Candidate.position_id == position.id).all()
            for candidate in candidates:
                if candidate.profile_image_url:
                    FileUploadService.delete_file(candidate.profile_image_url)
                db.delete(candidate)
            db.delete(position)
        
        db.delete(election)
        db.commit()
        
        return StandardResponse[dict](
            status=True,
            data={"deleted_election_id": election_id},
            error=None,
            message="Election deleted successfully"
        )
        
    except Exception as e:
        db.rollback()
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error deleting election"
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