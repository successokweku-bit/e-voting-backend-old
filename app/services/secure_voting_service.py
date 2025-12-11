"""
Secure voting service adapted for position-based elections
Create this as: app/services/secure_voting_service.py
"""
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime
from typing import Dict, Any, List, Optional
import json

from app.models.models import (
    User, Election, Candidate, Vote, Position,
    EncryptedVote, VoteCommitment, AuditLog, 
    VoteVerification, ElectionTally, UserRole, ElectionType
)
from app.core.encryption import (
    crypto_service, 
    encrypt_vote, 
    decrypt_and_verify_vote
)


class SecureVotingService:
    """Handles all secure voting operations for position-based elections"""
    
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
        
        # Helper function for timezone-aware datetime
        def get_current_utc_time():
            return datetime.now(timezone.utc)
        
        try:
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
            
            # Check election dates - FIX: Use timezone-aware datetime
            current_time = get_current_utc_time()
            
            if election.start_date and current_time < election.start_date.replace(tzinfo=timezone.utc):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "status": False,
                        "data": None,
                        "error": "Election has not started yet",
                        "message": "Vote failed"
                    }
                )
            
            if election.end_date and current_time > election.end_date.replace(tzinfo=timezone.utc):
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
            
            # 4. Check if user already voted for this position in this election
            existing_vote = db.query(EncryptedVote).filter(
                EncryptedVote.anonymous_voter_id == SecureVotingService._generate_anonymous_id(user.id),
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
            
            # 5. Generate anonymous voter ID (cannot be traced back)
            anonymous_voter_id = SecureVotingService._generate_anonymous_id(user.id)
            
            # 6. Encrypt vote data
            vote_data = {
                "user_id": user.id,
                "candidate_id": candidate_id,
                "timestamp": current_time.isoformat()
            }
            encrypted_data = SecureVotingService._encrypt_vote(json.dumps(vote_data))
            
            # 7. Generate vote hash for integrity
            vote_hash = SecureVotingService._generate_vote_hash(
                anonymous_voter_id, 
                election_id, 
                position_id, 
                candidate_id
            )
            
            # 8. Generate receipt for voter
            vote_receipt = SecureVotingService._generate_receipt()
            receipt_hash = SecureVotingService._hash_receipt(vote_receipt, vote_hash)
            
            # 9. Generate commitment for zero-knowledge proof
            commitment_factor = secrets.token_hex(32)
            commitment_hash = SecureVotingService._generate_commitment(
                vote_hash, 
                commitment_factor
            )
            
            # 10. Create encrypted vote record
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
                cast_at=current_time  # FIX: Use timezone-aware datetime
            )
            
            db.add(encrypted_vote)
            
            # 11. Store commitment separately
            vote_commitment = VoteCommitment(
                vote_hash=vote_hash,
                commitment_factor=commitment_factor
            )
            
            db.add(vote_commitment)
            
            # 12. Create audit log
            audit_log = AuditLog(
                action="VOTE_CAST",
                user_id=user.id,
                details=json.dumps({
                    "election_id": election_id,
                    "position_id": position_id,
                    "vote_receipt": vote_receipt,
                    "anonymous_id": anonymous_voter_id[:8] + "..."  # Partial for audit
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
            
            # 13. Return receipt to voter
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
    
    @staticmethod
    def verify_vote_receipt(
        db: Session,
        vote_receipt: str,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify a vote receipt (allows voters to confirm their vote was counted)
        
        Args:
            vote_receipt: Receipt code (e.g., VR-A1B2C3D4E5F6G7H8)
        
        Returns:
            Verification details (without revealing the vote)
        """
        # Find the encrypted vote
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
        
        # Record verification attempt
        verification = VoteVerification(
            vote_receipt=vote_receipt,
            ip_address=ip_address,
            verification_successful=True
        )
        db.add(verification)
        db.commit()
        
        # Return verification info (without revealing the vote)
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
    
    # ==================== VOTE TALLYING (SUPER ADMIN ONLY) ====================
    
    @staticmethod
    def tally_election_votes(
        db: Session,
        admin_user: User,
        election_id: int
    ) -> Dict[str, Any]:
        """
        Decrypt and tally votes for an election (Super Admin only)
        Tallies all positions in the election
        
        Args:
            admin_user: Admin performing the tally (must be SUPER_ADMIN)
            election_id: Election to tally
        
        Returns:
            Election results with integrity verification
        """
        # Verify admin has super admin role
        if admin_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": False,
                    "data": None,
                    "error": "Only Super Admins can tally votes",
                    "message": "Access denied"
                }
            )
        
        # Get election
        election = db.query(Election).filter(Election.id == election_id).first()
        if not election:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": False,
                    "data": None,
                    "error": "Election not found",
                    "message": "Tally failed"
                }
            )
        
        # Check if election has ended
        if datetime.utcnow() < election.end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": False,
                    "data": None,
                    "error": "Cannot tally votes until election has ended",
                    "message": "Tally failed"
                }
            )
        
        # Get all positions for this election
        positions = db.query(Position).filter(Position.election_id == election_id).all()
        
        if not positions:
            return {
                "success": True,
                "message": "No positions in this election",
                "results": []
            }
        
        # Tally results by position
        position_results = []
        total_votes_all = 0
        total_verified_all = 0
        total_failed_all = 0
        
        for position in positions:
            # Get encrypted votes for this position
            encrypted_votes = db.query(EncryptedVote).filter(
                EncryptedVote.election_id == election_id,
                EncryptedVote.position_id == position.id
            ).all()
            
            if not encrypted_votes:
                position_results.append({
                    "position_id": position.id,
                    "position_title": position.title,
                    "total_votes": 0,
                    "results": [],
                    "message": "No votes cast"
                })
                continue
            
            # Decrypt and count votes for this position
            candidate_votes = {}
            verified_count = 0
            failed_count = 0
            
            for enc_vote in encrypted_votes:
                try:
                    # Decrypt vote
                    vote_data = decrypt_and_verify_vote(
                        enc_vote.encrypted_vote_data,
                        enc_vote.vote_hash
                    )
                    
                    # Count the vote
                    candidate_id = vote_data["candidate_id"]
                    candidate_votes[candidate_id] = candidate_votes.get(candidate_id, 0) + 1
                    
                    # Mark as verified and tallied
                    enc_vote.verified = True
                    enc_vote.tallied = True
                    verified_count += 1
                    
                except Exception as e:
                    print(f"❌ Failed to decrypt/verify vote {enc_vote.id}: {str(e)}")
                    failed_count += 1
                    continue
            
            # Get candidate details for this position
            candidates = db.query(Candidate).filter(
                Candidate.position_id == position.id
            ).all()
            
            candidate_results = []
            for candidate in candidates:
                vote_count = candidate_votes.get(candidate.id, 0)
                candidate_results.append({
                    "candidate_id": candidate.id,
                    "candidate_name": candidate.user.full_name if candidate.user else "Unknown",
                    "party": candidate.party.acronym if candidate.party else "IND",
                    "vote_count": vote_count
                })
            
            # Sort by vote count
            candidate_results.sort(key=lambda x: x["vote_count"], reverse=True)
            
            position_results.append({
                "position_id": position.id,
                "position_title": position.title,
                "total_votes": len(encrypted_votes),
                "verified_votes": verified_count,
                "failed_votes": failed_count,
                "results": candidate_results
            })
            
            total_votes_all += len(encrypted_votes)
            total_verified_all += verified_count
            total_failed_all += failed_count
        
        # Create tally record
        tally_record = ElectionTally(
            election_id=election_id,
            tallied_by=admin_user.id,
            results_summary=json.dumps(position_results),
            total_votes_decrypted=total_votes_all,
            total_votes_verified=total_verified_all,
            integrity_check_passed=(total_failed_all == 0),
            audit_hash=crypto_service.generate_vote_hash({
                "election_id": election_id,
                "tallied_by": admin_user.id,
                "timestamp": datetime.utcnow().isoformat(),
                "results": position_results
            })
        )
        db.add(tally_record)
        
        # Create audit log
        SecureVotingService._create_audit_log(
            db=db,
            action="ELECTION_TALLIED",
            user_id=admin_user.id,
            details={
                "election_id": election_id,
                "total_votes": total_votes_all,
                "verified_votes": total_verified_all,
                "failed_votes": total_failed_all,
                "positions_tallied": len(positions)
            }
        )
        
        db.commit()
        
        return {
            "success": True,
            "message": "Election tallied successfully",
            "position_results": position_results,
            "statistics": {
                "total_votes": total_votes_all,
                "verified_votes": total_verified_all,
                "failed_votes": total_failed_all,
                "positions": len(positions),
                "integrity_passed": total_failed_all == 0
            }
        }
    
    # ==================== AUDIT TRAIL ====================
    
    @staticmethod
    def _create_audit_log(
        db: Session,
        action: str,
        user_id: int,
        details: Dict[str, Any],
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """
        Create audit log entry with hash chaining (blockchain-style)
        """
        # Get previous audit log
        previous_log = db.query(AuditLog).order_by(
            AuditLog.id.desc()
        ).first()
        
        previous_hash = previous_log.current_hash if previous_log else None
        
        # Generate current hash
        current_hash = crypto_service.generate_audit_hash(
            action=action,
            user_id=user_id,
            details=details,
            previous_hash=previous_hash
        )
        
        # Create audit log
        audit_log = AuditLog(
            action=action,
            user_id=user_id,
            details=json.dumps(details),
            previous_hash=previous_hash,
            current_hash=current_hash,
            ip_address=ip_address
        )
        
        db.add(audit_log)
        return audit_log
    
    @staticmethod
    def verify_audit_trail(db: Session) -> Dict[str, Any]:
        """
        Verify entire audit trail integrity (blockchain verification)
        
        Returns:
            Verification status and any broken links
        """
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
    
    # ==================== VOTING STATUS CHECKS ====================
    
    @staticmethod
    def check_user_voted_for_position(
        db: Session,
        user_id: int,
        election_id: int,
        position_id: int
    ) -> bool:
        """Check if user has voted for a specific position"""
        anonymous_id = crypto_service.generate_anonymous_voter_id(user_id, election_id, position_id)
        
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
                anonymous_id = crypto_service.generate_anonymous_voter_id(user_id, election_id, position.id)
                vote = db.query(EncryptedVote).filter(
                    EncryptedVote.anonymous_voter_id == anonymous_id
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