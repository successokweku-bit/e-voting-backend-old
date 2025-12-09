"""
Enhanced security module for e-voting system
Implements encryption, anonymization, and cryptographic operations
"""
from cryptography.fernet import Fernet
from datetime import datetime
import hashlib
import hmac
import secrets
import json
import os
from typing import Dict, Any, Optional

class VotingCrypto:
    """Handles all cryptographic operations for the voting system"""
    
    def __init__(self):
        """Initialize with encryption key from environment"""
        # Get encryption key from environment or generate new one
        key = os.getenv('VOTE_ENCRYPTION_KEY')
        if not key:
            # Generate a new key (for development only)
            key = Fernet.generate_key().decode()
            print(f"⚠️  WARNING: Generated new encryption key. Set VOTE_ENCRYPTION_KEY in .env")
            print(f"VOTE_ENCRYPTION_KEY={key}")
        
        if isinstance(key, str):
            key = key.encode()
        
        self.cipher = Fernet(key)
        
        # Secret salt for anonymization (from environment)
        self.anonymization_salt = os.getenv('ANONYMIZATION_SALT', 'default-salt-change-in-production').encode()
    
    # ==================== ENCRYPTION/DECRYPTION ====================
    
    def encrypt_vote_data(self, vote_data: Dict[str, Any]) -> str:
        """
        Encrypt vote data using Fernet (AES-128 CBC + HMAC-SHA256)
        
        Args:
            vote_data: Dictionary containing vote information
        
        Returns:
            Encrypted string (base64 encoded)
        """
        # Convert to JSON string
        json_data = json.dumps(vote_data, sort_keys=True)
        
        # Encrypt
        encrypted = self.cipher.encrypt(json_data.encode())
        
        return encrypted.decode()
    
    def decrypt_vote_data(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt vote data
        
        Args:
            encrypted_data: Encrypted string
        
        Returns:
            Original vote data dictionary
        """
        try:
            # Decrypt
            decrypted = self.cipher.decrypt(encrypted_data.encode())
            
            # Parse JSON
            vote_data = json.loads(decrypted.decode())
            
            return vote_data
        except Exception as e:
            raise ValueError(f"Failed to decrypt vote data: {str(e)}")
    
    # ==================== ANONYMIZATION ====================
    
    def generate_anonymous_voter_id(self, user_id: int, election_id: int, position_id: int) -> str:
        """
        Generate anonymous voter ID using HMAC-SHA256
        Cannot be traced back to original user
        
        Args:
            user_id: User's ID
            election_id: Election ID
            position_id: Position ID
        
        Returns:
            Anonymous voter ID (hex string)
        """
        # Combine user_id, election_id and position_id for unique anonymous ID per position
        message = f"{user_id}:{election_id}:{position_id}".encode()
        
        # Generate HMAC
        anonymous_id = hmac.new(
            self.anonymization_salt,
            message,
            hashlib.sha256
        ).hexdigest()
        
        return anonymous_id
    
    def verify_anonymous_voter_id(self, user_id: int, election_id: int, position_id: int, anonymous_id: str) -> bool:
        """
        Verify that an anonymous ID corresponds to a user, election and position
        
        Args:
            user_id: User's ID
            election_id: Election ID
            position_id: Position ID
            anonymous_id: Anonymous ID to verify
        
        Returns:
            True if valid, False otherwise
        """
        expected_id = self.generate_anonymous_voter_id(user_id, election_id, position_id)
        return hmac.compare_digest(expected_id, anonymous_id)
    
    # ==================== INTEGRITY HASHING ====================
    
    def generate_vote_hash(self, vote_data: Dict[str, Any]) -> str:
        """
        Generate SHA-256 hash of vote data for integrity verification
        
        Args:
            vote_data: Vote data dictionary
        
        Returns:
            SHA-256 hash (hex string)
        """
        # Convert to consistent JSON representation
        json_data = json.dumps(vote_data, sort_keys=True)
        
        # Generate hash
        vote_hash = hashlib.sha256(json_data.encode()).hexdigest()
        
        return vote_hash
    
    def verify_vote_integrity(self, vote_data: Dict[str, Any], stored_hash: str) -> bool:
        """
        Verify vote data hasn't been tampered with
        
        Args:
            vote_data: Decrypted vote data
            stored_hash: Hash stored with the vote
        
        Returns:
            True if integrity verified, False if tampered
        """
        calculated_hash = self.generate_vote_hash(vote_data)
        return hmac.compare_digest(calculated_hash, stored_hash)
    
    # ==================== RECEIPT GENERATION ====================
    
    def generate_vote_receipt(self, vote_hash: str, timestamp: datetime) -> str:
        """
        Generate unique vote receipt for voter verification
        
        Args:
            vote_hash: Hash of the vote
            timestamp: When vote was cast
        
        Returns:
            Vote receipt (format: VR-XXXXXXXXXXXXXXXX)
        """
        # Combine vote hash and timestamp
        receipt_data = f"{vote_hash}:{timestamp.isoformat()}".encode()
        
        # Generate receipt hash
        receipt_hash = hashlib.sha256(receipt_data).hexdigest()
        
        # Format as receipt (take first 16 chars for readability)
        receipt = f"VR-{receipt_hash[:16].upper()}"
        
        return receipt
    
    def generate_full_receipt_hash(self, vote_hash: str, timestamp: datetime) -> str:
        """
        Generate full receipt hash (stored in database)
        
        Args:
            vote_hash: Hash of the vote
            timestamp: When vote was cast
        
        Returns:
            Full receipt hash
        """
        receipt_data = f"{vote_hash}:{timestamp.isoformat()}".encode()
        return hashlib.sha256(receipt_data).hexdigest()
    
    # ==================== ZERO-KNOWLEDGE COMMITMENT ====================
    
    def generate_commitment(self, candidate_id: int, random_factor: Optional[str] = None) -> tuple[str, str]:
        """
        Generate zero-knowledge commitment
        Allows verification without revealing the vote
        
        Args:
            candidate_id: ID of candidate voted for
            random_factor: Random string (generated if not provided)
        
        Returns:
            Tuple of (commitment_hash, random_factor)
        """
        if random_factor is None:
            random_factor = secrets.token_hex(32)
        
        # Create commitment
        commitment_data = f"{candidate_id}:{random_factor}".encode()
        commitment_hash = hashlib.sha256(commitment_data).hexdigest()
        
        return commitment_hash, random_factor
    
    def verify_commitment(self, candidate_id: int, random_factor: str, commitment_hash: str) -> bool:
        """
        Verify a commitment matches the candidate
        
        Args:
            candidate_id: ID of candidate
            random_factor: Random factor used in commitment
            commitment_hash: Stored commitment hash
        
        Returns:
            True if commitment is valid
        """
        commitment_data = f"{candidate_id}:{random_factor}".encode()
        calculated_hash = hashlib.sha256(commitment_data).hexdigest()
        return hmac.compare_digest(calculated_hash, commitment_hash)
    
    # ==================== AUDIT TRAIL HASH CHAIN ====================
    
    def generate_audit_hash(self, action: str, user_id: int, details: Dict[str, Any], 
                          previous_hash: Optional[str] = None) -> str:
        """
        Generate hash for audit trail entry (blockchain-style)
        
        Args:
            action: Action performed
            user_id: User who performed action
            details: Action details
            previous_hash: Hash of previous audit entry (for chaining)
        
        Returns:
            Audit entry hash
        """
        # Create audit data
        audit_data = {
            "action": action,
            "user_id": user_id,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
            "previous_hash": previous_hash or "genesis"
        }
        
        # Generate hash
        json_data = json.dumps(audit_data, sort_keys=True)
        audit_hash = hashlib.sha256(json_data.encode()).hexdigest()
        
        return audit_hash
    
    def verify_audit_chain(self, current_entry: Dict[str, Any], 
                          previous_hash: str, stored_hash: str) -> bool:
        """
        Verify audit trail chain integrity
        
        Args:
            current_entry: Current audit entry data
            previous_hash: Previous entry's hash
            stored_hash: Hash stored for current entry
        
        Returns:
            True if chain is valid
        """
        calculated_hash = self.generate_audit_hash(
            current_entry["action"],
            current_entry["user_id"],
            current_entry["details"],
            previous_hash
        )
        return hmac.compare_digest(calculated_hash, stored_hash)


# Singleton instance
crypto_service = VotingCrypto()


# ==================== HELPER FUNCTIONS ====================

def encrypt_vote(user_id: int, candidate_id: int, election_id: int, position_id: int) -> Dict[str, Any]:
    """
    Complete vote encryption process
    
    Returns dictionary with all encrypted components:
    - anonymous_voter_id
    - encrypted_vote_data
    - vote_hash
    - vote_receipt
    - commitment_hash
    - commitment_factor (to be stored securely, separate from vote)
    """
    # Original vote data
    vote_data = {
        "user_id": user_id,
        "candidate_id": candidate_id,
        "election_id": election_id,
        "position_id": position_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # 1. Anonymize voter (per position)
    anonymous_id = crypto_service.generate_anonymous_voter_id(user_id, election_id, position_id)
    
    # 2. Encrypt vote data
    encrypted_data = crypto_service.encrypt_vote_data(vote_data)
    
    # 3. Generate integrity hash
    vote_hash = crypto_service.generate_vote_hash(vote_data)
    
    # 4. Generate receipt
    timestamp = datetime.utcnow()
    vote_receipt = crypto_service.generate_vote_receipt(vote_hash, timestamp)
    receipt_hash = crypto_service.generate_full_receipt_hash(vote_hash, timestamp)
    
    # 5. Generate commitment (zero-knowledge)
    commitment_hash, commitment_factor = crypto_service.generate_commitment(candidate_id)
    
    return {
        "anonymous_voter_id": anonymous_id,
        "encrypted_vote_data": encrypted_data,
        "vote_hash": vote_hash,
        "vote_receipt": vote_receipt,
        "receipt_hash": receipt_hash,
        "commitment_hash": commitment_hash,
        "commitment_factor": commitment_factor,
        "timestamp": timestamp
    }


def decrypt_and_verify_vote(encrypted_vote_data: str, stored_vote_hash: str) -> Dict[str, Any]:
    """
    Decrypt vote and verify integrity
    
    Raises ValueError if integrity check fails
    """
    # Decrypt
    vote_data = crypto_service.decrypt_vote_data(encrypted_vote_data)
    
    # Verify integrity
    if not crypto_service.verify_vote_integrity(vote_data, stored_vote_hash):
        raise ValueError("Vote integrity verification failed - possible tampering detected!")
    
    return vote_data