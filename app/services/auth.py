from sqlalchemy.orm import Session
from datetime import datetime, timedelta
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
                detail="Invalid credentials"
            )
        
        if not verify_password(login_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is inactive"
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
                    detail="Email already registered"
                )
            else:
                print(f"❌ NIN already registered: {user_data.nin}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="NIN already registered"
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
                detail="Invalid authentication credentials"
            )
        
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        
        user = db.query(User).filter(
            (User.email == username) | (User.nin == username)
        ).first()
        
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
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
        """Verify OTP code"""
        otp_record = db.query(OTP).filter(
            OTP.email == email,
            OTP.otp_code == otp_code,
            OTP.is_used == False,
            OTP.expires_at > datetime.utcnow()
        ).first()
        
        if otp_record:
            # Mark OTP as used
            otp_record.is_used = True
            db.commit()
            return True
        
        return False