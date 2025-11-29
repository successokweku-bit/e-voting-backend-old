try:
    from app.core.config import settings
    print("✅ Configuration loaded successfully!")
    print(f"Database URL: {settings.DATABASE_URL}")
    print(f"Debug mode: {settings.DEBUG}")
    print(f"Secret Key present: {bool(settings.SECRET_KEY)}")
except Exception as e:
    print(f"❌ Configuration error: {e}")
    import traceback
    traceback.print_exc()