from fix_database import fix_database
from create_super_admin import create_super_admin

def setup_system():
    print("🚀 Setting up E-Voting System...")
    print("=" * 50)
    
    # Step 1: Update database schema
    fix_database()
    
    print("\n" + "=" * 50)
    
    # Step 2: Create super admin
    admin = create_super_admin()
    
    print("\n" + "=" * 50)
    
    if admin:
        print("✅ System setup completed successfully!")
        print("\n📋 Next steps:")
        print("1. Start the server: python -m uvicorn app.main:app --reload")
        print("2. Login with admin@evoting.com / Admin123!")
        print("3. Access admin endpoints at /admin/*")
    else:
        print("❌ System setup failed!")

if __name__ == "__main__":
    setup_system()