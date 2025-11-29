from app.models.database import SessionLocal
from app.models.models import User, UserRole
from app.core.security import get_password_hash

def create_super_admin():
    db = SessionLocal()
    try:
        # Check if super admin already exists
        existing_admin = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if existing_admin:
            print("✅ Super admin already exists!")
            return
        
        # Create super admin
        super_admin = User(
            nin="00000000000",  # Special admin NIN
            email="admin@evoting.com",
            full_name="System Administrator",
            state_of_residence="FCT",  # Use your State enum value
            hashed_password=get_password_hash("Admin123!"),
            role=UserRole.SUPER_ADMIN,
            is_verified=True
        )
        
        db.add(super_admin)
        db.commit()
        print("✅ Super admin created successfully!")
        print("Email: admin@evoting.com")
        print("Password: Admin123!")
        
    except Exception as e:
        print(f"❌ Error creating super admin: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_super_admin()