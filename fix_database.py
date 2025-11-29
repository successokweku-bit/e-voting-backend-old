from app.models.database import engine
from app.models.models import Base
from app.core.config import settings

def fix_database():
    print(f"🔧 Using database: {settings.DATABASE_URL}")
    
    # Drop all tables
    print("🗑️  Dropping existing tables...")
    Base.metadata.drop_all(bind=engine)
    
    # Create tables with new schema (including role column)
    print("🔧 Creating tables with updated schema...")
    Base.metadata.create_all(bind=engine)
    
    print("✅ Database schema updated successfully!")
    print("📊 New tables created with role-based access control")

if __name__ == "__main__":
    fix_database()