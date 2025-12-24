from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query, UploadFile, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from app.models.database import get_db
from app.models.models import User, Election, Vote
from app.schemas.schemas import (
    ChangePasswordRequest, Token, LoginRequest, UserCreate, UserResponse, 
    ForgotPasswordRequest, ResetPasswordRequest, OTPResponse,
    StandardResponse
)
from app.core.security import create_access_token, get_password_hash, verify_password, verify_token
from app.core.config import settings
from app.services import email_service
from app.services.auth import AuthService, OTPService
from app.core.file_upload import FileUploadService

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


# ============================================================
# 🔐 LOGIN - FIXED VERSION
# ============================================================
@router.post("/token", response_model=StandardResponse[Token])
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    try:
        login_data = LoginRequest(username=form_data.username, password=form_data.password)
        user = AuthService.authenticate_user(db, login_data)

        if not user:
            return StandardResponse[Token](
                status=False,
                data=None,
                error="Invalid email or password",
                message="Login failed"
            )

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )

        # Convert SQLAlchemy model → Pydantic
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


# ============================================================
# 🧾 REGISTER USER
# ============================================================
@router.post("/register", response_model=StandardResponse[UserResponse])
async def register_user(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    try:
        user = AuthService.create_user(db, user_data)

        user_response = UserResponse.model_validate(user)

        return StandardResponse[UserResponse](
            status=True,
            data=user_response,
            error=None,
            message="User created successfully"
        )

    except HTTPException as he:
        return StandardResponse[UserResponse](
            status=False,
            data=None,
            error=he.detail,
            message="Registration failed"
        )

    except Exception as e:
        return StandardResponse[UserResponse](
            status=False,
            data=None,
            error=str(e),
            message="Internal server error during registration"
        )


# # ============================================================
# # 🔑 FORGOT PASSWORD
# # ============================================================
# @router.post("/forgot-password", response_model=StandardResponse[OTPResponse])
# async def forgot_password(
#     request: ForgotPasswordRequest,
#     background_tasks: BackgroundTasks,
#     db: Session = Depends(get_db)
# ):
#     try:
#         user = db.query(User).filter(User.email == request.email).first()

#         otp_response = OTPResponse(
#             message="If the email exists, a reset code has been sent",
#             email=request.email
#         )

#         if user:
#             otp_code = OTPService.create_otp_record(db, request.email)
#             print(f"OTP for {request.email}: {otp_code}")

#         return StandardResponse[OTPResponse](
#             status=True,
#             data=otp_response,
#             error=None,
#             message="Reset code sent successfully"
#         )

#     except Exception as e:
#         return StandardResponse[OTPResponse](
#             status=False,
#             data=None,
#             error=str(e),
#             message="Error sending reset code"
#         )


# # ============================================================
# # 🔒 RESET PASSWORD
# # ============================================================
# @router.post("/reset-password", response_model=StandardResponse[dict])
# async def reset_password(
#     request: ResetPasswordRequest,
#     db: Session = Depends(get_db)
# ):
#     try:
#         payload = verify_token(request.token)
#         if not payload:
#             return StandardResponse[dict](
#                 status=False,
#                 data=None,
#                 error="Invalid or expired reset token",
#                 message="Password reset failed"
#             )

#         email = payload.get("sub")
#         if not email:
#             return StandardResponse[dict](
#                 status=False,
#                 data=None,
#                 error="Invalid reset token",
#                 message="Password reset failed"
#             )

#         user = db.query(User).filter(User.email == email).first()
#         if not user:
#             return StandardResponse[dict](
#                 status=False,
#                 data=None,
#                 error="User not found",
#                 message="Password reset failed"
#             )

#         from app.core.security import get_password_hash
#         user.hashed_password = get_password_hash(request.new_password)
#         db.commit()

#         return StandardResponse[dict](
#             status=True,
#             data={"email": email},
#             error=None,
#             message="Password reset successfully"
#         )

#     except Exception as e:
#         db.rollback()
#         return StandardResponse[dict](
#             status=False,
#             data=None,
#             error=str(e),
#             message="Error resetting password"
#         )


# ============================================================
# 🔑 FORGOT PASSWORD (Updated to send Email)
# ============================================================
@router.post("/forgot-password", response_model=StandardResponse[OTPResponse])
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    try:
        user = db.query(User).filter(User.email == request.email).first()

        # We return a success message regardless of existence to prevent email enumeration attacks
        otp_response = OTPResponse(
            message="If the email exists, a reset code has been sent",
            email=request.email
        )

        if user:
            # Generate OTP
            otp_code = OTPService.create_otp_record(db, request.email)
            
            # Send Email via Background Task to keep response time fast
            background_tasks.add_task(
                email_service.send_password_reset_email,
                user.email,
                user.full_name,
                otp_code
            )

        return StandardResponse[OTPResponse](
            status=True,
            data=otp_response,
            message="Reset code sent successfully"
        )

    except Exception as e:
        return StandardResponse[OTPResponse](
            status=False,
            error=str(e),
            message="Error processing reset request"
        )

# ============================================================
# 🔒 RESET PASSWORD (Updated to verify OTP)
# ============================================================
@router.post("/reset-password", response_model=StandardResponse[dict])
async def reset_password(
    request: ResetPasswordRequest, # Ensure this schema has email, otp_code, and new_password
    db: Session = Depends(get_db)
):
    try:
        # 1. Verify the OTP record in the DB
        # Assuming OTPService.verify_otp checks if it exists, matches, and isn't expired
        is_valid = OTPService.verify_otp(db, request.email, request.otp_code)
        
        if not is_valid:
            return StandardResponse(
                status=False,
                error="INVALID_OTP",
                message="The reset code is invalid or has expired."
            )

        user = db.query(User).filter(User.email == request.email).first()
        if not user:
            return StandardResponse(status=False, error="USER_NOT_FOUND", message="User not found")

        # 2. Update Password
        user.hashed_password = get_password_hash(request.new_password)
        
        # 3. Clean up OTP (Optional: delete the code so it can't be reused)
        # OTPService.delete_otp(db, request.email)
        
        db.commit()

        return StandardResponse(
            status=True,
            data={"email": request.email},
            message="Password reset successfully. You can now log in with your new password."
        )

    except Exception as e:
        db.rollback()
        return StandardResponse(
            status=False,
            error=str(e),
            message="Error resetting password"
        )
    

# ============================================================
# 👤 GET CURRENT USER
# ============================================================
@router.get("/me", response_model=StandardResponse[UserResponse])
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    try:
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


# ============================================================
# 🚪 LOGOUT
# ============================================================
@router.post("/logout", response_model=StandardResponse[dict])
async def logout():
    return StandardResponse[dict](
        status=True,
        data=None,
        error=None,
        message="Successfully logged out"
    )


# ============================================================
# 🧪 DEBUG
# ============================================================
@router.post("/debug-test", response_model=StandardResponse[dict])
async def debug_test():
    return StandardResponse[dict](
        status=True,
        data={"message": "Debug endpoint working", "timestamp": "2024-01-01T00:00:00Z"},
        error=None,
        message="Debug test successful"
    )


# ============================================================
# 👥 PAGINATED USERS
# ============================================================
@router.get("/users/paginated", response_model=StandardResponse[dict])
async def get_users_paginated(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    try:
        total_users = db.query(User).count()
        users = db.query(User).offset(skip).limit(limit).all()

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


# ============================================================
# 🖼️ UPDATE PROFILE IMAGE
# ============================================================
@router.put("/me/profile-image", response_model=StandardResponse[UserResponse])
async def update_my_profile_image(
    profile_image: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    try:
        if current_user.profile_image_url:
            FileUploadService.delete_file(current_user.profile_image_url)

        profile_image_url = await FileUploadService.save_upload_file(
            profile_image, "uploads/profile_images"
        )
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


# ============================================================
# 🗳️ VOTER PROFILE
# ============================================================
@router.get("/me/voter-profile", response_model=StandardResponse[dict])
async def get_my_voter_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    try:
        user_votes = db.query(Vote).filter(Vote.user_id == current_user.id).all()
        total_votes_cast = len(user_votes)

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
                    "election_title": next(
                        (e.title for e in elections_participated if e.id == vote.election_id),
                        "Unknown Election"
                    ),
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


@router.post("/auth/change-password", response_model=StandardResponse[dict])
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Change password for the authenticated user
    """
    try:
        # 1. Verify that the old password provided matches the database
        if not verify_password(data.old_password, current_user.hashed_password):
            return StandardResponse(
                status=False,
                error="INVALID_PASSWORD",
                message="The old password you entered is incorrect."
            )

        # 2. Prevent using the same password again (Optional but recommended)
        if data.old_password == data.new_password:
            return StandardResponse(
                status=False,
                error="SAME_PASSWORD",
                message="New password cannot be the same as the old password."
            )

        # 3. Hash the new password and update the user record
        current_user.hashed_password = get_password_hash(data.new_password)
        
        db.add(current_user)
        db.commit()
        db.refresh(current_user)

        # 4. (Optional) Audit log for security
        # create_audit_log(db, user_id=current_user.id, action="PASSWORD_CHANGE")

        return StandardResponse(
            status=True,
            data={"user_id": current_user.id},
            message="Password updated successfully. Please log in again with your new credentials."
        )

    except Exception as e:
        db.rollback()
        return StandardResponse(
            status=False,
            error="SERVER_ERROR",
            message=f"An error occurred: {str(e)}"
        )