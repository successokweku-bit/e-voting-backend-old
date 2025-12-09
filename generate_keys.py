"""
Encryption Key Generator for E-Voting System
Run this ONCE to generate your encryption keys
"""
from cryptography.fernet import Fernet
import secrets

def generate_voting_keys():
    """Generate all required encryption keys for the voting system"""
    
    print("=" * 70)
    print("🔐 E-VOTING SYSTEM - ENCRYPTION KEY GENERATOR")
    print("=" * 70)
    print()
    
    # Generate encryption key for votes (Fernet/AES-128)
    encryption_key = Fernet.generate_key().decode()
    
    # Generate salt for anonymization (HMAC)
    anonymization_salt = secrets.token_hex(32)
    
    # Generate additional random secret for commitments
    commitment_secret = secrets.token_hex(32)
    
    print("✅ Keys generated successfully!")
    print()
    print("=" * 70)
    print("📝 ADD THESE TO YOUR .env FILE:")
    print("=" * 70)
    print()
    print(f"VOTE_ENCRYPTION_KEY={encryption_key}")
    print(f"ANONYMIZATION_SALT={anonymization_salt}")
    print(f"COMMITMENT_SECRET={commitment_secret}")
    print()
    print("=" * 70)
    print()
    print("⚠️  IMPORTANT SECURITY NOTES:")
    print("=" * 70)
    print()
    print("1. ⛔ NEVER commit these keys to version control (git)")
    print("2. 🔒 Store them securely (use environment variables)")
    print("3. 💾 Back up these keys in a secure location")
    print("4. 🚫 If keys are lost, old votes CANNOT be decrypted")
    print("5. 🔄 Use different keys for development and production")
    print("6. 👥 Limit access to these keys (super admin only)")
    print()
    print("=" * 70)
    print()
    print("📋 Next Steps:")
    print("=" * 70)
    print()
    print("1. Copy the keys above")
    print("2. Open your .env file")
    print("3. Paste the keys")
    print("4. Add .env to .gitignore if not already there")
    print("5. Run: pip install cryptography pycryptodome")
    print("6. Run database migrations")
    print("7. Test with a sample vote")
    print()
    print("=" * 70)
    print()
    
    # Create a sample .env file
    env_content = f"""# Database
DATABASE_URL=postgresql://user:password@localhost/evoting_db

# Security (JWT)
SECRET_KEY=your-jwt-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Vote Encryption Keys (Generated: {secrets.token_hex(8)})
VOTE_ENCRYPTION_KEY={encryption_key}
ANONYMIZATION_SALT={anonymization_salt}
COMMITMENT_SECRET={commitment_secret}

# CORS
ALLOWED_ORIGINS=["http://localhost:3000", "http://localhost:5173"]
DEBUG=True
"""
    
    # Save to file
    try:
        with open('.env.example', 'w') as f:
            f.write(env_content)
        print("✅ Created .env.example file (copy to .env and update as needed)")
        print()
    except Exception as e:
        print(f"⚠️  Could not create .env.example: {e}")
        print()
    
    return {
        "VOTE_ENCRYPTION_KEY": encryption_key,
        "ANONYMIZATION_SALT": anonymization_salt,
        "COMMITMENT_SECRET": commitment_secret
    }


def test_encryption(keys):
    """Test that the generated keys work correctly"""
    print("=" * 70)
    print("🧪 TESTING ENCRYPTION")
    print("=" * 70)
    print()
    
    try:
        # Test Fernet encryption
        cipher = Fernet(keys["VOTE_ENCRYPTION_KEY"].encode())
        
        test_data = b"Test vote data"
        encrypted = cipher.encrypt(test_data)
        decrypted = cipher.decrypt(encrypted)
        
        if decrypted == test_data:
            print("✅ Encryption/Decryption: PASSED")
        else:
            print("❌ Encryption/Decryption: FAILED")
            return False
        
        # Test HMAC
        import hmac
        import hashlib
        
        test_message = "user_id:123"
        hmac_result = hmac.new(
            keys["ANONYMIZATION_SALT"].encode(),
            test_message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if len(hmac_result) == 64:  # SHA-256 produces 64 hex characters
            print("✅ HMAC Anonymization: PASSED")
        else:
            print("❌ HMAC Anonymization: FAILED")
            return False
        
        print()
        print("=" * 70)
        print("✅ All encryption tests PASSED!")
        print("=" * 70)
        print()
        return True
        
    except Exception as e:
        print(f"❌ Encryption test FAILED: {e}")
        print()
        return False


if __name__ == "__main__":
    # Generate keys
    keys = generate_voting_keys()
    
    # Test the keys
    test_encryption(keys)
    
    print("🎉 Key generation complete! Follow the next steps above.")
    print()