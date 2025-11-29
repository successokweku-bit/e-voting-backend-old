import os
import subprocess
import sys

def setup_fresh():
    print("🚀 Starting fresh setup...")
    
    # Clear cache
    print("🗑️  Clearing cache...")
    os.system("find . -name '__pycache__' -type d -exec rm -rf {} +")
    os.system("find . -name '*.pyc' -delete")
    
    # Remove old database
    if os.path.exists("evoting.db"):
        os.remove("evoting.db")
        print("🗑️  Removed old database")
    
    # Import and create tables
    print("🔧 Creating database tables...")
    from app.core.database import engine, Base
    from app.models.models import Base as ModelsBase
    
    # Ensure we're using the same Base
    ModelsBase.metadata.create_all(bind=engine)
    print("✅ Database tables created!")
    
    # Create super admin
    print("👑 Creating super admin...")
    from create_super_admin import create_super_admin
    create_super_admin()
    
    # Create sample data
    print("📝 Creating sample data...")
    from create_sample_data import create_sample_data
    create_sample_data()
    
    print("🎉 Fresh setup completed!")
    print("\n📋 Next steps:")
    print("1. Start server: python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    print("2. Access: http://localhost:8000/docs")

if __name__ == "__main__":
    setup_fresh()