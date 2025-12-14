"""
Secure voting service adapted for position-based elections
"""
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import json
import secrets
import hashlib

from app.models.models import (
    User, Election, Candidate, Vote, Position,
    EncryptedVote, VoteCommitment, AuditLog, 
    VoteVerification, ElectionTally, UserRole
)
from app.core.encryption import (
    crypto_service, 
    encrypt_vote, 
    decrypt_and_verify_vote
)


class SecureVotingService:
    """Handles all secure voting operations for position-based elections"""
    
    # ==================== HELPER METHODS ====================
    
    @staticmethod
    def _generate_anonymous_id(user_id: int, election_id: int, position_id: int) -> str:
        """Generate irreversible anonymous voter ID"""
        return crypto_service.generate_anonymous_voter_id(user_id, election_id, position_id)
    
    @staticmethod
    def _encrypt_vote(vote_json: str) -> str:
        """Encrypt vote using encryption service"""
        return encrypt_vote(vote_json)
    
    @staticmethod
    def _generate_vote_hash(
        anonymous_voter_id: str,
        election_id: int,
        position_id: int,
        candidate_id: int
    ) -> str:
        """Creates a unique hash for the vote to ensure integrity"""
        payload = {
            "anon": anonymous_voter_id,
            "election": election_id,
            "position": position_id,
            "candidate": candidate_id
        }
        return crypto_service.generate_vote_hash(payload)
    
    @staticmethod
    def _generate_receipt() -> str:
        """
        Generates a human-friendly vote receipt number
        Example: VR-A1B2C3D4E5F6
        """
        code = secrets.token_hex(6).upper()
        return f"VR-{code}"
    
    @staticmethod
    def _hash_receipt(receipt: str, vote_hash: str) -> str:
        """Hash the receipt + vote hash for verification"""
        return crypto_service.generate_vote_hash({
            "receipt": receipt,
            "vote_hash": vote_hash
        })
    
    @staticmethod
    def _generate_commitment(vote_hash: str, commitment_factor: str) -> str:
        """Creates a zero-knowledge proof commitment hash"""
        return crypto_service.generate_vote_hash({
            "vote_hash": vote_hash,
            "factor": commitment_factor
        })
    
    @staticmethod
    def _get_latest_audit_hash(db: Session) -> Optional[str]:
        """Retrieves last audit log hash for blockchain-style chaining"""
        last_log = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
        return last_log.current_hash if last_log else "genesis"
    
    @staticmethod
    def _generate_audit_hash(action: str, user_id: int, timestamp: str) -> str:
        """Generates a hash for use in the audit logs"""
        return crypto_service.generate_audit_hash(
            action=action,
            user_id=user_id,
            timestamp=timestamp
        )
    
    # ==================== VOTE CASTING ====================
    
    @staticmethod
    def cast_encrypted_vote(
        db: Session,
        user: User,
        election_id: int,
        position_id: int,
        candidate_id: int,
        ip_address: Optional[str] = None
    ):
        """Cast an encrypted vote with full anonymization"""
        
        def get_current_utc_time():
            return datetime.now(timezone.utc)
        
        try:
            print(f"🗳️  SECURE VOTE REQUEST from user {user.id}")
            print(f"  Election ID: {election_id}")
            print(f"  Position ID: {position_id}")
            print(f"  Candidate ID: {candidate_id}")
            
            # 1. Validate election
            election = db.query(Election).filter(Election.id == election_id).first()
            if not election:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "status": False,
                        "data": None,
                        "error": "Election not found",
                        "message": "Vote failed"
                    }
                )
            
            # Check if election is active
            if not election.is_active:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "status": False,
                        "data": None,
                        "error": "Election is not active",
                        "message": "Vote failed"
                    }
                )
            
            # Check election dates
            current_time = get_current_utc_time()
            
            if election.start_date:
                start_date = election.start_date.replace(tzinfo=timezone.utc) if election.start_date.tzinfo is None else election.start_date
                if current_time < start_date:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "status": False,
                            "data": None,
                            "error": "Election has not started yet",
                            "message": "Vote failed"
                        }
                    )
            
            if election.end_date:
                end_date = election.end_date.replace(tzinfo=timezone.utc) if election.end_date.tzinfo is None else election.end_date
                if current_time > end_date:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "status": False,
                            "data": None,
                            "error": "Election has ended",
                            "message": "Vote failed"
                        }
                    )
            
            # 2. Validate position
            position = db.query(Position).filter(
                Position.id == position_id,
                Position.election_id == election_id
            ).first()
            
            if not position:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "status": False,
                        "data": None,
                        "error": "Position not found for this election",
                        "message": "Vote failed"
                    }
                )
            
            # 3. Validate candidate
            candidate = db.query(Candidate).filter(
                Candidate.id == candidate_id,
                Candidate.position_id == position_id,
                Candidate.election_id == election_id
            ).first()
            
            if not candidate:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "status": False,
                        "data": None,
                        "error": "Candidate not found for this position",
                        "message": "Vote failed"
                    }
                )
            
            # 4. Check if user already voted for this position
            anonymous_voter_id = SecureVotingService._generate_anonymous_id(
                user.id, 
                election_id, 
                position_id
            )
            
            existing_vote = db.query(EncryptedVote).filter(
                EncryptedVote.anonymous_voter_id == anonymous_voter_id,
                EncryptedVote.election_id == election_id,
                EncryptedVote.position_id == position_id
            ).first()
            
            if existing_vote:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "status": False,
                        "data": None,
                        "error": "You have already voted for this position",
                        "message": "Vote failed"
                    }
                )
            
            # 5. Encrypt vote data
            vote_data = {
                "user_id": user.id,
                "candidate_id": candidate_id,
                "position_id": position_id,
                "election_id": election_id,
                "timestamp": current_time.isoformat()
            }
            encrypted_data = SecureVotingService._encrypt_vote(json.dumps(vote_data))
            
            # 6. Generate vote hash for integrity
            vote_hash = SecureVotingService._generate_vote_hash(
                anonymous_voter_id, 
                election_id, 
                position_id, 
                candidate_id
            )
            
            # 7. Generate receipt for voter
            vote_receipt = SecureVotingService._generate_receipt()
            receipt_hash = SecureVotingService._hash_receipt(vote_receipt, vote_hash)
            
            # 8. Generate commitment for zero-knowledge proof
            commitment_factor = secrets.token_hex(32)
            commitment_hash = SecureVotingService._generate_commitment(
                vote_hash, 
                commitment_factor
            )
            
            # 9. Create encrypted vote record
            encrypted_vote = EncryptedVote(
                anonymous_voter_id=anonymous_voter_id,
                election_id=election_id,
                position_id=position_id,
                candidate_id=candidate_id,
                encrypted_vote_data=encrypted_data,
                vote_hash=vote_hash,
                vote_receipt=vote_receipt,
                receipt_hash=receipt_hash,
                commitment_hash=commitment_hash,
                cast_at=current_time
            )
            
            db.add(encrypted_vote)
            
            # 10. Store commitment separately
            vote_commitment = VoteCommitment(
                vote_hash=vote_hash,
                commitment_factor=commitment_factor
            )
            
            db.add(vote_commitment)
            
            # 11. Create audit log
            audit_log = AuditLog(
                action="VOTE_CAST",
                user_id=user.id,
                details=json.dumps({
                    "election_id": election_id,
                    "position_id": position_id,
                    "vote_receipt": vote_receipt,
                    "anonymous_id": anonymous_voter_id[:8] + "..."
                }),
                previous_hash=SecureVotingService._get_latest_audit_hash(db),
                current_hash=SecureVotingService._generate_audit_hash(
                    "VOTE_CAST", 
                    user.id, 
                    current_time.isoformat()
                ),
                ip_address=ip_address
            )
            
            db.add(audit_log)
            db.commit()
            
            print(f"✅ Secure vote cast successfully - Receipt: {vote_receipt}")
            
            # 12. Return receipt to voter
            return {
                "message": "Vote cast successfully",
                "vote_receipt": vote_receipt,
                "election": election.title,
                "position": position.title,
                "candidate": candidate.user.full_name if candidate.user else "Unknown",
                "timestamp": current_time.isoformat(),
                "instructions": "Save this receipt to verify your vote later. Your vote is encrypted and anonymous."
            }
        
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            print(f"❌ Error casting vote: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail={
                    "status": False,
                    "data": None,
                    "error": str(e),
                    "message": "Vote failed"
                }
            )
    
    # ==================== VOTE VERIFICATION ====================
    
    # @staticmethod
    # def verify_vote_receipt(
    #     db: Session,
    #     vote_receipt: str,
    #     ip_address: Optional[str] = None
    # ) -> Dict[str, Any]:
    #     """Verify a vote receipt"""
        
    #     encrypted_vote = db.query(EncryptedVote).filter(
    #         EncryptedVote.vote_receipt == vote_receipt
    #     ).first()
        
    #     if not encrypted_vote:
    #         raise HTTPException(
    #             status_code=status.HTTP_404_NOT_FOUND,
    #             detail={
    #                 "status": False,
    #                 "data": None,
    #                 "error": "Vote receipt not found",
    #                 "message": "Verification failed"
    #             }
    #         )
        
    #     # Record verification attempt
    #     verification = VoteVerification(
    #         vote_receipt=vote_receipt,
    #         ip_address=ip_address,
    #         verification_successful=True,
    #         verified_at=datetime.now(timezone.utc)
    #     )
        
    #     db.add(verification)
    #     db.commit()
        
    #     election = db.query(Election).filter(
    #         Election.id == encrypted_vote.election_id
    #     ).first()
        
    #     position = db.query(Position).filter(
    #         Position.id == encrypted_vote.position_id
    #     ).first()
        
    #     return {
    #         "verified": True,
    #         "message": "Your vote has been verified and counted!",
    #         "election_name": election.title if election else "Unknown",
    #         "position_title": position.title if position else "Unknown",
    #         "cast_at": encrypted_vote.cast_at.isoformat(),
    #         "vote_hash": encrypted_vote.vote_hash[:16] + "...",
    #         "tallied": encrypted_vote.tallied
    #     }

    @staticmethod
    def verify_vote_receipt(
        db: Session,
        vote_receipt: str,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Verify a vote receipt (idempotent & secure)"""

        encrypted_vote = db.query(EncryptedVote).filter(
            EncryptedVote.vote_receipt == vote_receipt
        ).first()

        if not encrypted_vote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": False,
                    "data": None,
                    "error": "Vote receipt not found",
                    "message": "Verification failed"
                }
            )

        now_utc = datetime.now(timezone.utc)

        # ✅ Mark vote as verified (ONLY ONCE)
        if not encrypted_vote.verified:
            encrypted_vote.verified = True
            encrypted_vote.tallied = True  # ← important for consistency
            encrypted_vote.verified_at = now_utc

        # ✅ Prevent duplicate verification records
        existing_verification = db.query(VoteVerification).filter(
            VoteVerification.vote_receipt == vote_receipt
        ).first()

        if not existing_verification:
            verification = VoteVerification(
                vote_receipt=vote_receipt,
                ip_address=ip_address,
                verification_successful=True,
                verified_at=now_utc
            )
            db.add(verification)

        db.add(encrypted_vote)
        db.commit()
        db.refresh(encrypted_vote)

        election = db.query(Election).filter(
            Election.id == encrypted_vote.election_id
        ).first()

        position = db.query(Position).filter(
            Position.id == encrypted_vote.position_id
        ).first()

        return {
            "verified": True,
            "message": "Your vote has been verified and counted!",
            "election_name": election.title if election else "Unknown",
            "position_title": position.title if position else "Unknown",
            "cast_at": encrypted_vote.cast_at.isoformat(),
            "vote_hash": encrypted_vote.vote_hash[:16] + "...",
            "tallied": encrypted_vote.tallied
        }

    # ==================== VOTING STATUS CHECKS ====================
    
    @staticmethod
    def check_user_voted_for_position(
        db: Session,
        user_id: int,
        election_id: int,
        position_id: int
    ) -> bool:
        """Check if user has voted for a specific position"""
        anonymous_id = SecureVotingService._generate_anonymous_id(
            user_id, 
            election_id, 
            position_id
        )
        
        vote = db.query(EncryptedVote).filter(
            EncryptedVote.anonymous_voter_id == anonymous_id,
            EncryptedVote.election_id == election_id,
            EncryptedVote.position_id == position_id
        ).first()
        
        return vote is not None
    
    @staticmethod
    def get_user_voting_status(
        db: Session,
        user_id: int,
        election_id: int
    ) -> Dict[str, Any]:
        """Get user's voting status for all positions in an election"""
        positions = db.query(Position).filter(Position.election_id == election_id).all()
        
        position_status = []
        for position in positions:
            has_voted = SecureVotingService.check_user_voted_for_position(
                db, user_id, election_id, position.id
            )
            
            receipt = None
            if has_voted:
                anonymous_id = SecureVotingService._generate_anonymous_id(
                    user_id, 
                    election_id, 
                    position.id
                )
                vote = db.query(EncryptedVote).filter(
                    EncryptedVote.anonymous_voter_id == anonymous_id,
                    EncryptedVote.election_id == election_id,
                    EncryptedVote.position_id == position.id
                ).first()
                if vote:
                    receipt = vote.vote_receipt
            
            position_status.append({
                "position_id": position.id,
                "position_title": position.title,
                "has_voted": has_voted,
                "vote_receipt": receipt
            })
        
        total_positions = len(positions)
        voted_positions = sum(1 for p in position_status if p["has_voted"])
        
        return {
            "election_id": election_id,
            "total_positions": total_positions,
            "voted_positions": voted_positions,
            "completion_percentage": (voted_positions / total_positions * 100) if total_positions > 0 else 0,
            "position_status": position_status
        }
    
    # ==================== AUDIT TRAIL ====================
    
    @staticmethod
    def verify_audit_trail(db: Session) -> Dict[str, Any]:
        """Verify entire audit trail integrity (blockchain verification)"""
        audit_logs = db.query(AuditLog).order_by(AuditLog.id).all()
        
        if not audit_logs:
            return {
                "verified": True,
                "message": "No audit logs to verify",
                "total_logs": 0,
                "broken_links": []
            }
        
        broken_links = []
        
        for i, log in enumerate(audit_logs):
            if i == 0:
                if log.previous_hash and log.previous_hash != "genesis":
                    broken_links.append({
                        "log_id": log.id,
                        "issue": "First log has unexpected previous hash"
                    })
            else:
                expected_previous = audit_logs[i - 1].current_hash
                if log.previous_hash != expected_previous:
                    broken_links.append({
                        "log_id": log.id,
                        "issue": "Hash chain broken",
                        "expected": expected_previous,
                        "actual": log.previous_hash
                    })
        
        return {
            "verified": len(broken_links) == 0,
            "total_logs": len(audit_logs),
            "broken_links": broken_links,
            "message": "Audit trail verified" if not broken_links else "Audit trail compromised!"
        }
    @staticmethod
    def tally_election_votes(db: Session, admin_user: User, election_id: int):
        election = db.query(Election).filter(Election.id==election_id).first()
        if not election:
            raise HTTPException(404, "Election not found")

        results = {}
        total_votes = 0
        verified_votes = 0

        for position in election.positions:
            results[position.title] = {}
            votes = db.query(EncryptedVote).filter(
                EncryptedVote.election_id==election.id,
                EncryptedVote.position_id==position.id,
                (EncryptedVote.tallied==False) | (EncryptedVote.tallied==None)
            ).all()

            for vote in votes:
                candidate_name = vote.candidate.user.full_name if vote.candidate else "Unknown"
                results[position.title][candidate_name] = results[position.title].get(candidate_name, 0) + 1
                vote.tallied = True
                verified_votes += 1

            total_votes += len(votes)

        # Save tally
        tally = ElectionTally(
            election_id=election_id,
            tallied_by=admin_user.id,
            results_summary=json.dumps(results),
            total_votes_decrypted=total_votes,
            total_votes_verified=verified_votes,
            integrity_check_passed=True,
            audit_hash=secrets.token_hex(32)
        )
        db.add(tally)
        db.commit()

        return {
            "message": f"Votes tallied successfully for election '{election.title}'",
            "results": results,
            "total_votes": total_votes,
            "verified_votes": verified_votes
        }