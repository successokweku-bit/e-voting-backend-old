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

from typing import List, Optional
import json

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
    nin: Optional[str] = Form(None, description="National Identification Number"),
    email: Optional[str] = Form(None, description="User's email address"),
    full_name: Optional[str] = Form(None, description="User's full name"),
    state_of_residence: Optional[str] = Form(None, description="State of residence"),
    date_of_birth: Optional[str] = Form(None, description="Date of birth (YYYY-MM-DD)"),
    is_active: Optional[bool] = Form(None, description="User active status"),
    is_verified: Optional[bool] = Form(None, description="User verification status"),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update user profile information."""
    try:
        # DEBUG: Print what we received
        print(f"Received data - NIN: {nin}, Email: {email}, Full Name: {full_name}")
        print(f"State: {state_of_residence}, DOB: {date_of_birth}")
        print(f"Active: {is_active}, Verified: {is_verified}")
        
        from app.models.models import State
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return StandardResponse[UserResponse](
                status=False,
                data=None,
                error="User not found",
                message="User update failed"
            )
        
        # Track what fields are being updated
        updated_fields = []
        
        # Update NIN if provided
        if nin:
            existing_user = db.query(User).filter(User.nin == nin, User.id != user_id).first()
            if existing_user:
                return StandardResponse[UserResponse](
                    status=False,
                    data=None,
                    error="NIN already exists",
                    message="User update failed"
                )
            user.nin = nin
            updated_fields.append("nin")
        
        # Update email if provided
        if email:
            existing_user = db.query(User).filter(User.email == email, User.id != user_id).first()
            if existing_user:
                return StandardResponse[UserResponse](
                    status=False,
                    data=None,
                    error="Email already exists",
                    message="User update failed"
                )
            user.email = email
            updated_fields.append("email")
        
        # Update full name if provided
        if full_name:
            user.full_name = full_name
            updated_fields.append("full_name")
        
        # Update state of residence if provided
        if state_of_residence:
            valid_states = [state.value for state in State]
            if state_of_residence not in valid_states:
                return StandardResponse[UserResponse](
                    status=False,
                    data=None,
                    error=f"Invalid state. Must be one of: {', '.join(valid_states)}",
                    message="User update failed"
                )
            user.state_of_residence = state_of_residence
            updated_fields.append("state_of_residence")
        
        # Update date of birth if provided
        if date_of_birth:
            try:
                for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%SZ"]:
                    try:
                        parsed_date = datetime.strptime(date_of_birth, fmt)
                        user.date_of_birth = parsed_date
                        updated_fields.append("date_of_birth")
                        break
                    except ValueError:
                        continue
                else:
                    user.date_of_birth = datetime.fromisoformat(date_of_birth.replace('Z', '+00:00'))
                    updated_fields.append("date_of_birth")
            except Exception as date_error:
                return StandardResponse[UserResponse](
                    status=False,
                    data=None,
                    error=f"Invalid date format. Use YYYY-MM-DD. Error: {str(date_error)}",
                    message="User update failed"
                )
        
        # Update is_active if provided
        if is_active is not None:
            if user_id == current_user.id and not is_active:
                return StandardResponse[UserResponse](
                    status=False,
                    data=None,
                    error="Cannot deactivate your own account",
                    message="User update failed"
                )
            user.is_active = is_active
            updated_fields.append("is_active")
        
        # Update is_verified if provided
        if is_verified is not None:
            user.is_verified = is_verified
            updated_fields.append("is_verified")
        
        print(f"Updated fields: {updated_fields}")  # DEBUG
        
        db.commit()
        db.refresh(user)
        
        user_response = UserResponse.model_validate(user)
        
        return StandardResponse[UserResponse](
            status=True,
            data=user_response,
            error=None,
            message=f"User profile updated successfully. Updated: {', '.join(updated_fields) if updated_fields else 'no fields'}"
        )
        
    except Exception as e:
        db.rollback()
        print(f"Error: {str(e)}")  # DEBUG
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
@router.post("/candidates", response_model=StandardResponse[dict], summary="Create Candidate")
async def create_candidate(
    user_id: int = Form(..., description="User ID of the candidate"),
    bio: Optional[str] = Form(None, description="Candidate biography"),
    party_id: Optional[int] = Form(None, description="Political party ID"),
    position_id: int = Form(..., description="Position ID"),
    manifestos: Optional[str] = Form(None, description="JSON string of manifestos array: [{\"title\": \"...\", \"description\": \"...\"}]"),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new candidate from an existing user with manifestos.
    
    **Admin only** - Requires admin authentication.
    
    **Manifestos Format**: Send as JSON string array
```json
    [
      {"title": "Education Reform", "description": "Improve schools..."},
      {"title": "Healthcare", "description": "Better healthcare access..."}
    ]
```
    """
    try:
        # Check if user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="User not found",
                message="Candidate creation failed"
            )
        
        # Check if user is already a candidate
        existing_candidate = db.query(Candidate).filter(Candidate.user_id == user_id).first()
        if existing_candidate:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="User is already a candidate",
                message="Candidate creation failed"
            )
        
        # Verify position exists
        from app.models.models import Position
        position = db.query(Position).filter(Position.id == position_id).first()
        if not position:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Position not found",
                message="Candidate creation failed"
            )
        
        # Verify party exists if provided
        if party_id:
            party = db.query(PoliticalParty).filter(PoliticalParty.id == party_id).first()
            if not party:
                return StandardResponse[dict](
                    status=False,
                    data=None,
                    error="Political party not found",
                    message="Candidate creation failed"
                )
        
        # Parse and validate manifestos
        manifestos_list = []
        if manifestos:
            try:
                manifestos_list = json.loads(manifestos)
                
                # Validate manifesto structure
                if not isinstance(manifestos_list, list):
                    return StandardResponse[dict](
                        status=False,
                        data=None,
                        error="Manifestos must be an array",
                        message="Candidate creation failed"
                    )
                
                for idx, item in enumerate(manifestos_list):
                    if not isinstance(item, dict):
                        return StandardResponse[dict](
                            status=False,
                            data=None,
                            error=f"Manifesto item {idx + 1} must be an object",
                            message="Candidate creation failed"
                        )
                    if 'title' not in item or 'description' not in item:
                        return StandardResponse[dict](
                            status=False,
                            data=None,
                            error=f"Manifesto item {idx + 1} must have 'title' and 'description' fields",
                            message="Candidate creation failed"
                        )
                    if not item['title'] or not item['description']:
                        return StandardResponse[dict](
                            status=False,
                            data=None,
                            error=f"Manifesto item {idx + 1} title and description cannot be empty",
                            message="Candidate creation failed"
                        )
                        
            except json.JSONDecodeError as e:
                return StandardResponse[dict](
                    status=False,
                    data=None,
                    error=f"Invalid JSON format for manifestos: {str(e)}",
                    message="Candidate creation failed"
                )
        
        # Create candidate
        candidate = Candidate(
            user_id=user_id,
            bio=bio,
            party_id=party_id,
            position_id=position_id,
            manifestos=manifestos_list
        )
        
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        
        return StandardResponse[dict](
            status=True,
            data={
                "candidate_id": candidate.id,
                "user_id": candidate.user_id,
                "user_name": user.full_name,
                "user_email": user.email,
                "profile_image_url": user.profile_image_url,
                "bio": candidate.bio,
                "party_id": candidate.party_id,
                "party_name": candidate.party.name if candidate.party else None,
                "position_id": candidate.position_id,
                "position_title": candidate.position.title,
                "manifestos": candidate.manifestos,
                "manifesto_count": len(candidate.manifestos) if candidate.manifestos else 0
            },
            error=None,
            message="Candidate created successfully"
        )
        
    except Exception as e:
        db.rollback()
        print(f"Error creating candidate: {str(e)}")  # DEBUG
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error creating candidate"
        )

@router.get("/candidates", response_model=StandardResponse[List[dict]], summary="Get All Candidates")
async def get_all_candidates(
    position_id: Optional[int] = Query(None, description="Filter by position ID"),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get all candidates with their user information and manifestos."""
    try:
        query = db.query(Candidate)
        
        if position_id:
            query = query.filter(Candidate.position_id == position_id)
        
        candidates = query.all()
        
        candidates_data = []
        for candidate in candidates:
            candidates_data.append({
                "candidate_id": candidate.id,
                "user_id": candidate.user_id,
                "user_name": candidate.user.full_name,
                "user_email": candidate.user.email,
                "profile_image_url": candidate.user.profile_image_url,
                "bio": candidate.bio,
                "party_id": candidate.party_id,
                "party_name": candidate.party.name if candidate.party else None,
                "party_acronym": candidate.party.acronym if candidate.party else None,
                "position_id": candidate.position_id,
                "position_title": candidate.position.title,
                "manifestos": candidate.manifestos if candidate.manifestos else [],
                "manifesto_count": len(candidate.manifestos) if candidate.manifestos else 0
            })
        
        return StandardResponse[List[dict]](
            status=True,
            data=candidates_data,
            error=None,
            message=f"Retrieved {len(candidates_data)} candidates"
        )
        
    except Exception as e:
        return StandardResponse[List[dict]](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving candidates"
        )

@router.get("/candidates/{candidate_id}", response_model=StandardResponse[dict], summary="Get Candidate by ID")
async def get_candidate_by_id(
    candidate_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get specific candidate by ID with full details."""
    try:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Candidate not found",
                message="Candidate retrieval failed"
            )
        
        candidate_data = {
            "candidate_id": candidate.id,
            "user_id": candidate.user_id,
            "user_name": candidate.user.full_name,
            "user_email": candidate.user.email,
            "profile_image_url": candidate.user.profile_image_url,
            "bio": candidate.bio,
            "party_id": candidate.party_id,
            "party_name": candidate.party.name if candidate.party else None,
            "party_acronym": candidate.party.acronym if candidate.party else None,
            "position_id": candidate.position_id,
            "position_title": candidate.position.title,
            "manifestos": candidate.manifestos if candidate.manifestos else [],
            "manifesto_count": len(candidate.manifestos) if candidate.manifestos else 0
        }
        
        return StandardResponse[dict](
            status=True,
            data=candidate_data,
            error=None,
            message="Candidate retrieved successfully"
        )
        
    except Exception as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving candidate"
        )

@router.put("/candidates/{candidate_id}", response_model=StandardResponse[dict], summary="Update Candidate")
async def update_candidate(
    candidate_id: int,
    bio: Optional[str] = Form(None, description="Candidate biography"),
    party_id: Optional[int] = Form(None, description="Political party ID"),
    position_id: Optional[int] = Form(None, description="Position ID"),
    manifestos: Optional[str] = Form(None, description="JSON string of manifestos array"),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Update candidate information including manifestos.
    
    **Note**: Updating manifestos replaces the entire array.
    """
    try:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Candidate not found",
                message="Candidate update failed"
            )
        
        updated_fields = []
        
        # Update bio if provided
        if bio is not None:
            candidate.bio = bio
            updated_fields.append("bio")
        
        # Update party if provided
        if party_id:
            party = db.query(PoliticalParty).filter(PoliticalParty.id == party_id).first()
            if not party:
                return StandardResponse[dict](
                    status=False,
                    data=None,
                    error="Political party not found",
                    message="Candidate update failed"
                )
            candidate.party_id = party_id
            updated_fields.append("party")
        
        # Update position if provided
        if position_id:
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
            updated_fields.append("position")
        
        # Update manifestos if provided
        if manifestos is not None:
            try:
                manifestos_list = json.loads(manifestos)
                
                # Validate manifesto structure
                if not isinstance(manifestos_list, list):
                    return StandardResponse[dict](
                        status=False,
                        data=None,
                        error="Manifestos must be an array",
                        message="Candidate update failed"
                    )
                
                for idx, item in enumerate(manifestos_list):
                    if not isinstance(item, dict):
                        return StandardResponse[dict](
                            status=False,
                            data=None,
                            error=f"Manifesto item {idx + 1} must be an object",
                            message="Candidate update failed"
                        )
                    if 'title' not in item or 'description' not in item:
                        return StandardResponse[dict](
                            status=False,
                            data=None,
                            error=f"Manifesto item {idx + 1} must have 'title' and 'description' fields",
                            message="Candidate update failed"
                        )
                
                candidate.manifestos = manifestos_list
                updated_fields.append("manifestos")
                
            except json.JSONDecodeError as e:
                return StandardResponse[dict](
                    status=False,
                    data=None,
                    error=f"Invalid JSON format for manifestos: {str(e)}",
                    message="Candidate update failed"
                )
        
        db.commit()
        db.refresh(candidate)
        
        return StandardResponse[dict](
            status=True,
            data={
                "candidate_id": candidate.id,
                "user_id": candidate.user_id,
                "user_name": candidate.user.full_name,
                "bio": candidate.bio,
                "party_id": candidate.party_id,
                "party_name": candidate.party.name if candidate.party else None,
                "position_id": candidate.position_id,
                "position_title": candidate.position.title,
                "manifestos": candidate.manifestos if candidate.manifestos else [],
                "updated_fields": updated_fields
            },
            error=None,
            message=f"Candidate updated successfully. Updated: {', '.join(updated_fields)}"
        )
        
    except Exception as e:
        db.rollback()
        print(f"Error updating candidate: {str(e)}")  # DEBUG
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error updating candidate"
        )

@router.delete("/candidates/{candidate_id}", response_model=StandardResponse[dict], summary="Delete Candidate")
async def delete_candidate(
    candidate_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Delete candidate. Cannot delete if candidate has received votes."""
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
                error=f"Cannot delete candidate with {votes} votes. Deactivate instead.",
                message="Candidate deletion failed"
            )
        
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
@router.get("/elections", response_model=StandardResponse[List[dict]], summary="Get All Elections")
async def get_all_elections(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get all elections with optional filtering.
    
    **Admin only** - Requires admin authentication.
    """
    try:
        query = db.query(Election)
        
        if is_active is not None:
            query = query.filter(Election.is_active == is_active)
        
        elections = query.order_by(Election.created_at.desc()).all()
        
        elections_data = []
        for election in elections:
            elections_data.append({
                "election_id": election.id,
                "title": election.title,
                "description": election.description,
                "election_type": election.election_type,
                "state": election.state,
                "is_active": election.is_active,
                "start_date": election.start_date.isoformat() if election.start_date else None,
                "end_date": election.end_date.isoformat() if election.end_date else None,
                "created_at": election.created_at.isoformat() if election.created_at else None,
                "position_count": len(election.positions) if hasattr(election, 'positions') else 0
            })
        
        return StandardResponse[List[dict]](
            status=True,
            data=elections_data,
            error=None,
            message=f"Retrieved {len(elections_data)} elections"
        )
        
    except Exception as e:
        return StandardResponse[List[dict]](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving elections"
        )

@router.get("/elections/{election_id}", response_model=StandardResponse[dict], summary="Get Election by ID")
async def get_election_by_id(
    election_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get specific election by ID with detailed information.
    
    **Admin only** - Requires admin authentication.
    """
    try:
        election = db.query(Election).filter(Election.id == election_id).first()
        
        if not election:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Election not found",
                message="Election retrieval failed"
            )
        
        election_data = {
            "election_id": election.id,
            "title": election.title,
            "description": election.description,
            "election_type": election.election_type,
            "state": election.state,
            "is_active": election.is_active,
            "start_date": election.start_date.isoformat() if election.start_date else None,
            "end_date": election.end_date.isoformat() if election.end_date else None,
            "created_at": election.created_at.isoformat() if election.created_at else None,
            "position_count": len(election.positions) if hasattr(election, 'positions') else 0,
            "positions": [
                {
                    "position_id": pos.id,
                    "title": pos.title,
                    "description": pos.description,
                    "candidate_count": len(pos.candidates) if hasattr(pos, 'candidates') else 0
                } for pos in election.positions
            ] if hasattr(election, 'positions') else []
        }
        
        return StandardResponse[dict](
            status=True,
            data=election_data,
            error=None,
            message="Election retrieved successfully"
        )
        
    except Exception as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving election"
        )

@router.post("/elections", response_model=StandardResponse[dict], summary="Create Election")
async def create_election(
    title: str = Form(..., description="Election title"),
    description: Optional[str] = Form(None, description="Election description"),
    election_type: str = Form(..., description="Type of election (e.g., Presidential, Gubernatorial)"),
    state: Optional[str] = Form(None, description="State (if state election)"),
    is_active: bool = Form(True, description="Active status"),
    start_date: Optional[datetime] = Form(None, description="Start date"),
    end_date: Optional[datetime] = Form(None, description="End date"),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new election.
    
    **Admin only** - Requires admin authentication.
    """
    try:
        # Validate dates
        if start_date and end_date and start_date >= end_date:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="End date must be after start date",
                message="Election creation failed"
            )
        
        # Create election
        election = Election(
            title=title,
            description=description,
            election_type=election_type,
            state=state,
            is_active=is_active,
            start_date=start_date,
            end_date=end_date
        )
        
        db.add(election)
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
                "start_date": election.start_date.isoformat() if election.start_date else None,
                "end_date": election.end_date.isoformat() if election.end_date else None
            },
            error=None,
            message="Election created successfully"
        )
        
    except Exception as e:
        db.rollback()
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error creating election"
        )
    
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

# === POSITION MANAGEMENT ===
@router.post("/positions", response_model=StandardResponse[dict], summary="Create Position")
async def create_position(
    title: str = Form(..., description="Position title"),
    description: Optional[str] = Form(None, description="Position description"),
    election_id: int = Form(..., description="Election ID"),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new position for an election.
    
    **Admin only** - Requires admin authentication.
    """
    try:
        from app.models.models import Position
        
        # Verify election exists
        election = db.query(Election).filter(Election.id == election_id).first()
        if not election:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Election not found",
                message="Position creation failed"
            )
        
        # Create position
        position = Position(
            title=title,
            description=description,
            election_id=election_id
        )
        
        db.add(position)
        db.commit()
        db.refresh(position)
        
        return StandardResponse[dict](
            status=True,
            data={
                "position_id": position.id,
                "title": position.title,
                "description": position.description,
                "election_id": position.election_id
            },
            error=None,
            message="Position created successfully"
        )
        
    except Exception as e:
        db.rollback()
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error creating position"
        )

@router.get("/positions", response_model=StandardResponse[List[dict]], summary="Get All Positions")
async def get_all_positions(
    election_id: Optional[int] = Query(None, description="Filter by election ID"),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get all positions, optionally filtered by election."""
    try:
        from app.models.models import Position
        
        query = db.query(Position)
        
        if election_id:
            query = query.filter(Position.election_id == election_id)
        
        positions = query.all()
        
        positions_data = []
        for position in positions:
            positions_data.append({
                "position_id": position.id,
                "title": position.title,
                "description": position.description,
                "election_id": position.election_id,
                "election_title": position.election.title,
                "candidate_count": len(position.candidates)
            })
        
        return StandardResponse[List[dict]](
            status=True,
            data=positions_data,
            error=None,
            message=f"Retrieved {len(positions_data)} positions"
        )
        
    except Exception as e:
        return StandardResponse[List[dict]](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving positions"
        )

@router.get("/positions/{position_id}", response_model=StandardResponse[dict], summary="Get Position by ID")
async def get_position_by_id(
    position_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get specific position by ID."""
    try:
        from app.models.models import Position
        
        position = db.query(Position).filter(Position.id == position_id).first()
        if not position:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Position not found",
                message="Position retrieval failed"
            )
        
        position_data = {
            "position_id": position.id,
            "title": position.title,
            "description": position.description,
            "election_id": position.election_id,
            "election_title": position.election.title,
            "candidate_count": len(position.candidates)
        }
        
        return StandardResponse[dict](
            status=True,
            data=position_data,
            error=None,
            message="Position retrieved successfully"
        )
        
    except Exception as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving position"
        )

@router.put("/positions/{position_id}", response_model=StandardResponse[dict], summary="Update Position")
async def update_position(
    position_id: int,
    title: Optional[str] = Form(None, description="Position title"),
    description: Optional[str] = Form(None, description="Position description"),
    election_id: Optional[int] = Form(None, description="Election ID"),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update position information."""
    try:
        from app.models.models import Position
        
        position = db.query(Position).filter(Position.id == position_id).first()
        if not position:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Position not found",
                message="Position update failed"
            )
        
        # Update fields if provided
        if title:
            position.title = title
        
        if description is not None:
            position.description = description
        
        if election_id:
            election = db.query(Election).filter(Election.id == election_id).first()
            if not election:
                return StandardResponse[dict](
                    status=False,
                    data=None,
                    error="Election not found",
                    message="Position update failed"
                )
            position.election_id = election_id
        
        db.commit()
        db.refresh(position)
        
        return StandardResponse[dict](
            status=True,
            data={
                "position_id": position.id,
                "title": position.title,
                "description": position.description,
                "election_id": position.election_id
            },
            error=None,
            message="Position updated successfully"
        )
        
    except Exception as e:
        db.rollback()
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error updating position"
        )

@router.delete("/positions/{position_id}", response_model=StandardResponse[dict], summary="Delete Position")
async def delete_position(
    position_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Delete position and all associated candidates."""
    try:
        from app.models.models import Position
        
        position = db.query(Position).filter(Position.id == position_id).first()
        if not position:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Position not found",
                message="Position deletion failed"
            )
        
        # Check if position has candidates with votes
        from app.models.models import Vote
        for candidate in position.candidates:
            votes = db.query(Vote).filter(Vote.candidate_id == candidate.id).count()
            if votes > 0:
                return StandardResponse[dict](
                    status=False,
                    data=None,
                    error=f"Cannot delete position with candidates who have received votes",
                    message="Position deletion failed"
                )
        
        # Delete candidates first
        for candidate in position.candidates:
            db.delete(candidate)
        
        db.delete(position)
        db.commit()
        
        return StandardResponse[dict](
            status=True,
            data={"deleted_position_id": position_id},
            error=None,
            message="Position deleted successfully"
        )
        
    except Exception as e:
        db.rollback()
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error deleting position"
        )

# === ADMIN DASHBOARD ENDPOINTS ===

@router.get("/dashboard/stats", response_model=StandardResponse[dict], summary="Get Dashboard Statistics")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive admin dashboard statistics.
    
    **Admin only** - Requires admin authentication.
    """
    try:
        from app.models.models import Vote, Position
        
        # User statistics
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        inactive_users = total_users - active_users
        admin_users = db.query(User).filter(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN])).count()
        regular_users = total_users - admin_users
        
        # Election statistics
        total_elections = db.query(Election).count()
        active_elections = db.query(Election).filter(Election.is_active == True).count()
        
        # Party statistics
        total_parties = db.query(PoliticalParty).count()
        
        # Candidate statistics
        total_candidates = db.query(Candidate).count()
        
        # Vote statistics
        total_votes = db.query(Vote).count()
        
        # Position statistics
        total_positions = db.query(Position).count()
        
        stats = {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": inactive_users,
            "admin_users": admin_users,
            "regular_users": regular_users,
            "total_elections": total_elections,
            "active_elections": active_elections,
            "total_parties": total_parties,
            "total_candidates": total_candidates,
            "total_votes": total_votes,
            "total_positions": total_positions
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