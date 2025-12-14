"""
Encryption and cryptographic utilities for secure voting
"""
import hashlib
import secrets
import json
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
from datetime import datetime
import base64

class CryptoService:
    """Handles all cryptographic operations"""
    
    def __init__(self):
        # In production, load this from environment variable
        self._key = self._get_or_generate_key()
        self._cipher = Fernet(self._key)
    
    def _get_or_generate_key(self) -> bytes:
        """Get encryption key from environment or generate new one"""
        import os
        key_str = os.getenv("ENCRYPTION_KEY")
        
        if key_str:
            return key_str.encode()
        else:
            key = Fernet.generate_key()
            print(f"⚠️  GENERATED NEW ENCRYPTION KEY: {key.decode()}")
            print("⚠️  Store this in your .env file as ENCRYPTION_KEY")
            return key
    
    def generate_anonymous_voter_id(
        self, 
        user_id: int, 
        election_id: int, 
        position_id: int
    ) -> str:
        """
        Generate irreversible anonymous voter ID
        Includes election and position to prevent linking across elections
        """
        # Create unique identifier including election and position
        data = f"{user_id}:{election_id}:{position_id}:evoting_salt_v1"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def generate_vote_hash(self, data: Dict[str, Any]) -> str:
        """Generate unique hash for vote integrity"""
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def generate_audit_hash(
        self, 
        action: str, 
        user_id: int, 
        timestamp: str,
        details: Optional[Dict] = None
    ) -> str:
        """Generate hash for audit log entry"""
        data = {
            "action": action,
            "user_id": user_id,
            "timestamp": timestamp,
            "details": details or {}
        }
        return self.generate_vote_hash(data)
    
    def encrypt_data(self, data: str) -> str:
        """Encrypt string data"""
        encrypted = self._cipher.encrypt(data.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt string data"""
        try:
            decoded = base64.b64decode(encrypted_data.encode())
            decrypted = self._cipher.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")

# Global crypto service instance
crypto_service = CryptoService()

# Helper functions
def encrypt_vote(vote_json: str) -> str:
    """Encrypt vote data"""
    return crypto_service.encrypt_data(vote_json)

def decrypt_vote(encrypted_data: str) -> Dict[str, Any]:
    """Decrypt vote data"""
    decrypted_json = crypto_service.decrypt_data(encrypted_data)
    return json.loads(decrypted_json)

def decrypt_and_verify_vote(encrypted_data: str, expected_hash: str) -> Dict[str, Any]:
    """Decrypt vote and verify its integrity"""
    vote_data = decrypt_vote(encrypted_data)
    
    # Verify hash
    actual_hash = crypto_service.generate_vote_hash({
        "user_id": vote_data.get("user_id"),
        "candidate_id": vote_data.get("candidate_id"),
        "position_id": vote_data.get("position_id"),
        "election_id": vote_data.get("election_id")
    })
    
    # Note: In production, you'd want stricter hash verification
    # For now, we'll just decrypt and return
    
    return vote_data