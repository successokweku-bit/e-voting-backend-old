"""
Quick test script to verify secure voting features are working
Run this AFTER completing all implementation steps

Usage:
    python test_secure_features.py
"""
import sys
import os
from dotenv import load_dotenv

# Force reload .env
load_dotenv(override=True)

print("VOTE_ENCRYPTION_KEY:", os.getenv('VOTE_ENCRYPTION_KEY'))
print("ANONYMIZATION_SALT:", os.getenv('ANONYMIZATION_SALT'))

def test_imports():
    """Test if all required modules can be imported"""
    print("🧪 Test 1: Checking imports...")
    
    try:
        from app.core.encryption import crypto_service, encrypt_vote
        print("   ✅ encryption.py imported successfully")
    except ImportError as e:
        print(f"   ❌ Failed to import encryption.py: {e}")
        return False
    
    try:
        from app.services.secure_voting_service import SecureVotingService
        print("   ✅ secure_voting_service.py imported successfully")
    except ImportError as e:
        print(f"   ❌ Failed to import secure_voting_service.py: {e}")
        return False
    
    try:
        from app.models.models import EncryptedVote, AuditLog, VoteCommitment
        print("   ✅ New models imported successfully")
    except ImportError as e:
        print(f"   ❌ Failed to import new models: {e}")
        return False
    
    return True


def test_encryption_keys():
    """Test if encryption keys are set"""
    print("\n🔑 Test 2: Checking encryption keys...")
    
    vote_key = os.getenv('VOTE_ENCRYPTION_KEY')
    anon_salt = os.getenv('ANONYMIZATION_SALT')
    
    if not vote_key:
        print("   ❌ VOTE_ENCRYPTION_KEY not set in environment")
        print("   Run: python generate_keys.py")
        return False
    
    if not anon_salt:
        print("   ❌ ANONYMIZATION_SALT not set in environment")
        print("   Run: python generate_keys.py")
        return False
    
    print(f"   ✅ VOTE_ENCRYPTION_KEY is set ({len(vote_key)} chars)")
    print(f"   ✅ ANONYMIZATION_SALT is set ({len(anon_salt)} chars)")
    
    return True


def test_encryption_functionality():
    """Test basic encryption/decryption"""
    print("\n🔐 Test 3: Testing encryption functionality...")
    
    try:
        from app.core.encryption import crypto_service
        
        # Test vote data encryption
        test_data = {
            "user_id": 123,
            "candidate_id": 456,
            "election_id": 789,
            "position_id": 1
        }
        
        # Encrypt
        encrypted = crypto_service.encrypt_vote_data(test_data)
        print(f"   ✅ Data encrypted successfully")
        
        # Verify it's actually encrypted
        if "user_id" in encrypted or "123" in encrypted:
            print("   ❌ Data appears to be in plaintext!")
            return False
        
        # Decrypt
        decrypted = crypto_service.decrypt_vote_data(encrypted)
        print(f"   ✅ Data decrypted successfully")
        
        # Verify
        if decrypted == test_data:
            print("   ✅ Encryption/Decryption verified")
        else:
            print("   ❌ Decrypted data doesn't match original")
            return False
        
        return True
        
    except Exception as e:
        print(f"   ❌ Encryption test failed: {e}")
        return False


def test_anonymization():
    """Test voter anonymization"""
    print("\n🎭 Test 4: Testing voter anonymization...")
    
    try:
        from app.core.encryption import crypto_service
        
        user_id = 123
        election_id = 456
        position_id = 1
        
        # Generate anonymous ID
        anon_id_1 = crypto_service.generate_anonymous_voter_id(user_id, election_id, position_id)
        anon_id_2 = crypto_service.generate_anonymous_voter_id(user_id, election_id, position_id)
        
        # Should be deterministic
        if anon_id_1 != anon_id_2:
            print("   ❌ Anonymous IDs are not deterministic")
            return False
        
        print(f"   ✅ Anonymous ID generated: {anon_id_1[:16]}...")
        
        # Should not contain user ID
        if str(user_id) in anon_id_1:
            print("   ❌ User ID appears in anonymous ID")
            return False
        
        print("   ✅ Anonymous ID does not contain user ID")
        
        # Different inputs should give different outputs
        anon_id_3 = crypto_service.generate_anonymous_voter_id(user_id, election_id, position_id + 1)
        if anon_id_1 == anon_id_3:
            print("   ❌ Different inputs produce same anonymous ID")
            return False
        
        print("   ✅ Different inputs produce different IDs")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Anonymization test failed: {e}")
        return False


def test_vote_hashing():
    """Test vote integrity hashing"""
    print("\n#️⃣ Test 5: Testing vote integrity hashing...")
    
    try:
        from app.core.encryption import crypto_service
        
        vote_data = {
            "user_id": 123,
            "candidate_id": 456,
            "election_id": 789,
            "position_id": 1
        }
        
        # Generate hash
        hash1 = crypto_service.generate_vote_hash(vote_data)
        print(f"   ✅ Vote hash generated: {hash1[:16]}...")
        
        # Verify integrity
        if crypto_service.verify_vote_integrity(vote_data, hash1):
            print("   ✅ Vote integrity verified")
        else:
            print("   ❌ Vote integrity verification failed")
            return False
        
        # Test tampering detection
        tampered_data = vote_data.copy()
        tampered_data["candidate_id"] = 999
        
        if crypto_service.verify_vote_integrity(tampered_data, hash1):
            print("   ❌ Failed to detect tampering")
            return False
        
        print("   ✅ Tampering detected successfully")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Hashing test failed: {e}")
        return False


def test_receipt_generation():
    """Test vote receipt generation"""
    print("\n🎫 Test 6: Testing receipt generation...")
    
    try:
        from app.core.encryption import crypto_service
        from datetime import datetime
        
        vote_hash = "abc123def456"
        timestamp = datetime.utcnow()
        
        # Generate receipt
        receipt = crypto_service.generate_vote_receipt(vote_hash, timestamp)
        
        # Verify format
        if not receipt.startswith("VR-"):
            print(f"   ❌ Invalid receipt format: {receipt}")
            return False
        
        # Verify length (VR- + 16 hex chars = 19)
        if len(receipt) != 19:
            print(f"   ❌ Invalid receipt length: {len(receipt)}")
            return False
        
        print(f"   ✅ Receipt generated: {receipt}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Receipt generation failed: {e}")
        return False


def test_complete_vote_encryption():
    """Test complete vote encryption process"""
    print("\n🗳️  Test 7: Testing complete vote encryption...")
    
    try:
        from app.core.encryption import encrypt_vote
        
        result = encrypt_vote(
            user_id=123,
            candidate_id=456,
            election_id=789,
            position_id=1
        )
        
        required_keys = [
            'anonymous_voter_id',
            'encrypted_vote_data',
            'vote_hash',
            'vote_receipt',
            'receipt_hash',
            'commitment_hash',
            'commitment_factor',
            'timestamp'
        ]
        
        for key in required_keys:
            if key not in result:
                print(f"   ❌ Missing key: {key}")
                return False
        
        print("   ✅ All components generated:")
        print(f"      - Anonymous ID: {result['anonymous_voter_id'][:16]}...")
        print(f"      - Receipt: {result['vote_receipt']}")
        print(f"      - Hash: {result['vote_hash'][:16]}...")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Complete encryption failed: {e}")
        return False


def test_database_tables():
    """Test if database tables exist"""
    print("\n🗄️  Test 8: Checking database tables...")
    
    try:
        from app.models.database import engine
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        required_tables = [
            'encrypted_votes',
            'vote_commitments',
            'audit_logs',
            'vote_verifications',
            'user_sessions',
            'election_tallies'
        ]
        
        missing_tables = []
        for table in required_tables:
            if table in tables:
                print(f"   ✅ Table exists: {table}")
            else:
                print(f"   ❌ Table missing: {table}")
                missing_tables.append(table)
        
        if missing_tables:
            print(f"\n   Run database migrations to create missing tables:")
            print(f"   alembic revision --autogenerate -m 'add secure voting'")
            print(f"   alembic upgrade head")
            return False
        
        return True
        
    except Exception as e:
        print(f"   ❌ Database check failed: {e}")
        print("   Make sure your database is configured correctly")
        return False


def main():
    """Run all tests"""
    print("=" * 70)
    print("🧪 SECURE VOTING FEATURES - TEST SUITE")
    print("=" * 70)
    print()
    
    tests = [
        ("Imports", test_imports),
        ("Encryption Keys", test_encryption_keys),
        ("Encryption Functionality", test_encryption_functionality),
        ("Voter Anonymization", test_anonymization),
        ("Vote Integrity Hashing", test_vote_hashing),
        ("Receipt Generation", test_receipt_generation),
        ("Complete Vote Encryption", test_complete_vote_encryption),
        ("Database Tables", test_database_tables),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {test_name}")
    
    print()
    print(f"Passed: {passed}/{total}")
    print()
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Your secure voting system is ready.")
        print()
        print("Next steps:")
        print("1. Start your server: uvicorn app.main:app --reload")
        print("2. Test the API endpoints")
        print("3. Update your frontend to use the new endpoints")
    else:
        print("⚠️  SOME TESTS FAILED. Please review the errors above.")
        print()
        print("Common issues:")
        print("1. Missing encryption keys → Run generate_keys.py")
        print("2. Missing tables → Run database migrations")
        print("3. Import errors → Check file paths and names")
    
    print("=" * 70)
    print()
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)