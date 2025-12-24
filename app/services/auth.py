from sqlalchemy.orm import Session
from datetime import datetime, timedelta,timezone
from fastapi import HTTPException, status
from app.models.models import User, OTP
from app.core.security import verify_password, get_password_hash, verify_token
from app.schemas.schemas import LoginRequest, UserCreate

class AuthService:
    
    @staticmethod
    def authenticate_user(db: Session, login_data: LoginRequest) -> User:
        """Authenticate user by email/NIN and password"""
        # Try to find user by email or NIN
        user = db.query(User).filter(
            (User.email == login_data.username) | (User.nin == login_data.username)
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": False,
                    "data": None,
                    "error": "Invalid email/NIN or password",
                    "message": "Authentication failed"
                }
            )
        
        if not verify_password(login_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": False,
                    "data": None,
                    "error": "Invalid email/NIN or password",
                    "message": "Authentication failed"
                }
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": False,
                    "data": None,
                    "error": "Account is inactive. Please contact administrator.",
                    "message": "Account access denied"
                }
            )
        
        return user
    
    @staticmethod
    def create_user(db: Session, user_data: UserCreate) -> User:
        """Create a new user"""
        print(f"🔧 Creating user: {user_data.email}")
        
        # Check if user already exists
        existing_user = db.query(User).filter(
            (User.email == user_data.email) | (User.nin == user_data.nin)
        ).first()
        
        if existing_user:
            if existing_user.email == user_data.email:
                print(f"❌ Email already registered: {user_data.email}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": False,
                        "data": None,
                        "error": "Email address is already registered",
                        "message": "Registration failed"
                    }
                )
            else:
                print(f"❌ NIN already registered: {user_data.nin}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": False,
                        "data": None,
                        "error": "NIN is already registered",
                        "message": "Registration failed"
                    }
                )
        
        # Create new user - preserve role from request or default to USER
        hashed_password = get_password_hash(user_data.password)
        user = User(
            nin=user_data.nin,
            email=user_data.email,
            full_name=user_data.full_name,
            state_of_residence=user_data.state_of_residence.value,
            hashed_password=hashed_password,
            role=user_data.role  # Include role from request
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        print(f"✅ User created successfully: {user.email} (ID: {user.id}, Role: {user.role.value})")
        return user
   
    @staticmethod
    def get_current_user(db: Session, token: str) -> User:
        """Get current user from JWT token"""
        payload = verify_token(token)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": False,
                    "data": None,
                    "error": "Invalid or expired authentication token",
                    "message": "Authentication failed"
                }
            )
        
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": False,
                    "data": None,
                    "error": "Invalid token payload",
                    "message": "Authentication failed"
                }
            )
        
        user = db.query(User).filter(
            (User.email == username) | (User.nin == username)
        ).first()
        
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": False,
                    "data": None,
                    "error": "User account not found",
                    "message": "Authentication failed"
                }
            )
        
        return user

class OTPService:
    
    @staticmethod
    def generate_otp() -> str:
        """Generate a 6-digit OTP"""
        import random
        return str(random.randint(100000, 999999))
    
    @staticmethod
    def create_otp_record(db: Session, email: str) -> str:
        """Create OTP record in database"""
        # Invalidate any existing OTPs for this email
        db.query(OTP).filter(OTP.email == email).update({"is_used": True})
        
        # Generate new OTP
        otp_code = OTPService.generate_otp()
        expires_at = datetime.utcnow() + timedelta(minutes=10)  # OTP valid for 10 minutes
        
        otp_record = OTP(
            email=email,
            otp_code=otp_code,
            expires_at=expires_at
        )
        
        db.add(otp_record)
        db.commit()
        
        return otp_code
    
    @staticmethod
    def verify_otp(db: Session, email: str, otp_code: str) -> bool:
        """Verify OTP code and check if it has expired"""
        
        # 1. Fetch the record matching the email and code
        otp_record = db.query(OTP).filter(
            OTP.email == email,
            OTP.otp_code == otp_code,
            OTP.is_used == False
        ).first()
        
        if not otp_record:
            return False # Code doesn't exist or was already used

        # 2. Check if the current time is past the expiry time
        # Use timezone-aware 'now' to match your model's timezone=True
        now = datetime.now(timezone.utc) 
        
        if now > otp_record.expires_at:
            # Code is expired
            return False
            
        # 3. If we reached here, the code is valid. Mark it as used.
        otp_record.is_used = True
        db.commit()
        return True