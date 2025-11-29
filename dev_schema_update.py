import os
from app.models.database import engine
from app.models.models import Base

def update_schema():
    print("🔄 Updating database schema...")
    
    # Remove old database
    if os.path.exists("evoting.db"):
        os.remove("evoting.db")
        print("🗑️  Removed old database")
    
    # Create new database with latest schema
    Base.metadata.create_all(bind=engine)
    print("✅ Created new database with latest schema")
    
    # Verify
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"📊 Tables created: {tables}")
    
    # Check users table columns
    columns = inspector.get_columns('users')
    print("🔍 Users table columns:")
    for col in columns:
        print(f"   - {col['name']}")

if __name__ == "__main__":
    update_schema()