
from app.core.database import get_db
from app.schemas.schemas import ForgotPasswordRequest, OTPResponse, ResetPasswordRequest, StandardResponse
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query, UploadFile, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

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
    
    
@router.get("/states", response_model=StandardResponse[dict])
async def get_all_states():
    """Get list of all Nigerian states - Public endpoint"""
    try:
        from app.models.models import State
        
        states = [
            {
                "name": state.value,
                "code": state.name
            }
            for state in State
        ]
        
        return StandardResponse[dict](
            status=True,
            data={
                "total": len(states),
                "states": states
            },
            error=None,
            message="States retrieved successfully"
        )
        
    except Exception as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving states"
        )