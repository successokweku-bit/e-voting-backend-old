from app.models.database import engine
from app.models.models import Base

def check_schema():
    inspector = engine.dialect.inspector(engine)
    
    print("📊 Current Database Schema:")
    table_names = inspector.get_table_names()
    print(f"Tables: {table_names}")
    
    if 'users' in table_names:
        print("\n🔍 Users table columns:")
        columns = inspector.get_columns('users')
        for col in columns:
            print(f"  - {col['name']} ({col['type']})")

if __name__ == "__main__":
    check_schema()