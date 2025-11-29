from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks,Query, UploadFile, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from app.models.database import get_db
from app.models.models import User
from app.schemas.schemas import (
    Token, LoginRequest, UserCreate, UserResponse, 
    ForgotPasswordRequest, ResetPasswordRequest, OTPResponse,
    StandardResponse
)
from app.core.security import create_access_token, verify_token
from app.core.config import settings
from app.services.auth import AuthService, OTPService

from app.core.file_upload import FileUploadService
from fastapi import UploadFile, File

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# Dependency to get current user
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    return AuthService.get_current_user(db, token)

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

@router.post("/token", response_model=StandardResponse[Token])
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login and get access token"""
    try:
        login_data = LoginRequest(username=form_data.username, password=form_data.password)
        user = AuthService.authenticate_user(db, login_data)
        
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )
        
        # Convert SQLAlchemy model to Pydantic model using model_validate
        user_response = UserResponse.model_validate(user)
        
        token_data = Token(
            access_token=access_token,
            token_type="bearer",
            user=user_response
        )
        
        return StandardResponse[Token](
            status=True,
            data=token_data,
            error=None,
            message="Login successful"
        )
        
    except HTTPException as he:
        return StandardResponse[Token](
            status=False,
            data=None,
            error=he.detail,
            message="Login failed"
        )
    except Exception as e:
        return StandardResponse[Token](
            status=False,
            data=None,
            error=str(e),
            message="Internal server error during login"
        )

@router.post("/register", response_model=StandardResponse[UserResponse])
async def register_user(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Register a new user"""
    try:
        print(f"🔧 Registration attempt for: {user_data.email}")
        
        user = AuthService.create_user(db, user_data)
        print(f"✅ User created with ID: {user.id}")
        
        # Convert SQLAlchemy model to Pydantic model using model_validate
        user_response = UserResponse.model_validate(user)
        print(f"✅ User response created")
        
        return StandardResponse[UserResponse](
            status=True,
            data=user_response,
            error=None,
            message="User created successfully"
        )
        
    except HTTPException as he:
        # Return standardized error response for HTTP exceptions
        print(f"❌ HTTP Exception: {he.detail}")
        return StandardResponse[UserResponse](
            status=False,
            data=None,
            error=he.detail,
            message="Registration failed"
        )
    except Exception as e:
        # Log unexpected errors
        print(f"❌ Unexpected error in registration: {e}")
        import traceback
        traceback.print_exc()
        return StandardResponse[UserResponse](
            status=False,
            data=None,
            error=str(e),
            message="Internal server error during registration"
        )

@router.post("/forgot-password", response_model=StandardResponse[OTPResponse])
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Request password reset OTP"""
    try:
        # Check if user exists
        user = db.query(User).filter(User.email == request.email).first()
        if not user:
            # Don't reveal that email doesn't exist
            otp_response = OTPResponse(
                message="If the email exists, a reset code has been sent",
                email=request.email
            )
            return StandardResponse[OTPResponse](
                status=True,
                data=otp_response,
                error=None,
                message="Reset instructions sent if email exists"
            )
        
        # Generate OTP
        otp_code = OTPService.create_otp_record(db, request.email)
        
        # In a real application, you would send the OTP via email
        # background_tasks.add_task(send_otp_email, request.email, otp_code)
        
        print(f"OTP for {request.email}: {otp_code}")  # Remove this in production
        
        otp_response = OTPResponse(
            message="If the email exists, a reset code has been sent",
            email=request.email
        )
        
        return StandardResponse[OTPResponse](
            status=True,
            data=otp_response,
            error=None,
            message="Reset code sent successfully"
        )
        
    except Exception as e:
        return StandardResponse[OTPResponse](
            status=False,
            data=None,
            error=str(e),
            message="Error sending reset code"
        )

@router.post("/reset-password", response_model=StandardResponse[dict])
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Reset password with OTP"""
    try:
        # For now, we'll skip OTP verification for simplicity
        # In production, you would verify the OTP first
        
        # Verify token (in this case, we're using the OTP as token for simplicity)
        # This should be enhanced with proper token verification
        payload = verify_token(request.token)
        if not payload:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Invalid or expired reset token",
                message="Password reset failed"
            )
        
        email = payload.get("sub")
        if not email:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Invalid reset token",
                message="Password reset failed"
            )
        
        # Update user password
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="User not found",
                message="Password reset failed"
            )
        
        from app.core.security import get_password_hash
        user.hashed_password = get_password_hash(request.new_password)
        db.commit()
        
        return StandardResponse[dict](
            status=True,
            data={"email": email},
            error=None,
            message="Password reset successfully"
        )
        
    except Exception as e:
        db.rollback()
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error resetting password"
        )

@router.get("/me", response_model=StandardResponse[UserResponse])
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """Get current user information"""
    try:
        # Convert SQLAlchemy model to Pydantic model using model_validate
        user_response = UserResponse.model_validate(current_user)
        
        return StandardResponse[UserResponse](
            status=True,
            data=user_response,
            error=None,
            message="User data retrieved successfully"
        )
    except Exception as e:
        return StandardResponse[UserResponse](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving user data"
        )

@router.post("/logout", response_model=StandardResponse[dict])
async def logout():
    """Logout user (client should discard token)"""
    return StandardResponse[dict](
        status=True,
        data=None,
        error=None,
        message="Successfully logged out"
    )

# Debug endpoint
@router.post("/debug-test", response_model=StandardResponse[dict])
async def debug_test():
    """Debug endpoint to test basic functionality"""
    return StandardResponse[dict](
        status=True,
        data={"message": "Debug endpoint working", "timestamp": "2024-01-01T00:00:00Z"},
        error=None,
        message="Debug test successful"
    )

# fetch all the users 
@router.get("/users/paginated", response_model=StandardResponse[dict])
async def get_users_paginated(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get users with pagination"""
    try:
        # Get total count
        total_users = db.query(User).count()
        
        # Get paginated users
        users = db.query(User).offset(skip).limit(limit).all()
        
        # Convert to response models
        users_response = [UserResponse.model_validate(user) for user in users]
        
        return StandardResponse[dict](
            status=True,
            data={
                "users": users_response,
                "pagination": {
                    "skip": skip,
                    "limit": limit,
                    "total": total_users,
                    "has_more": (skip + limit) < total_users
                }
            },
            error=None,
            message=f"Retrieved {len(users_response)} users"
        )
        
    except Exception as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving users"
        )
    

@router.put("/me/profile-image", response_model=StandardResponse[UserResponse])
async def update_my_profile_image(
    profile_image: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile image"""
    try:
        # Delete old profile image if exists
        if current_user.profile_image_url:
            FileUploadService.delete_file(current_user.profile_image_url)
        
        # Save new profile image
        profile_image_url = await FileUploadService.save_upload_file(profile_image, "uploads/profile_images")
        current_user.profile_image_url = profile_image_url
        
        db.commit()
        db.refresh(current_user)
        
        user_response = UserResponse.model_validate(current_user)
        
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

@router.get("/me/voter-profile", response_model=StandardResponse[dict])
async def get_my_voter_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's voter profile with voting history"""
    try:
        # Get user's voting history
        user_votes = db.query(Vote).filter(Vote.user_id == current_user.id).all()
        total_votes_cast = len(user_votes)
        
        # Get elections participated in
        election_ids = [vote.election_id for vote in user_votes]
        elections_participated = db.query(Election).filter(Election.id.in_(election_ids)).all()
        election_titles = [election.title for election in elections_participated]
        
        voter_profile = {
            "user": UserResponse.model_validate(current_user),
            "total_votes_cast": total_votes_cast,
            "elections_participated": election_titles,
            "voting_history": [
                {
                    "election_id": vote.election_id,
                    "election_title": next((e.title for e in elections_participated if e.id == vote.election_id), "Unknown Election"),
                    "voted_at": vote.created_at
                }
                for vote in user_votes
            ]
        }
        
        return StandardResponse[dict](
            status=True,
            data=voter_profile,
            error=None,
            message="Voter profile retrieved successfully"
        )
        
    except Exception as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving voter profile"
        )