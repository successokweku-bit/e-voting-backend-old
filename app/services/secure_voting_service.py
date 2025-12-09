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
    ) -> Dict[str, Any]:
        """
        Cast an encrypted, anonymous vote for a specific position
        
        Returns:
            Dictionary with vote_receipt and confirmation message
        """
        # Verify election exists and is active
        election = db.query(Election).filter(Election.id == election_id).first()
        if not election:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": False,
                    "data": None,
                    "error": "Election not found",
                    "message": "Vote failed"
                }
            )
        
        # Check if election is active
        now = datetime.utcnow()
        if now < election.start_date or now > election.end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": False,
                    "data": None,
                    "error": "Election is not currently active",
                    "message": "Vote failed"
                }
            )
        
        # Verify position exists and belongs to this election
        position = db.query(Position).filter(
            Position.id == position_id,
            Position.election_id == election_id
        ).first()
        if not position:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": False,
                    "data": None,
                    "error": "Position not found in this election",
                    "message": "Vote failed"
                }
            )
        
        # Verify candidate exists and belongs to this position
        candidate = db.query(Candidate).filter(
            Candidate.id == candidate_id,
            Candidate.position_id == position_id
        ).first()
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": False,
                    "data": None,
                    "error": "Candidate not found in this position",
                    "message": "Vote failed"
                }
            )
        
        # Check state eligibility (for state/local elections)
        if election.election_type != ElectionType.FEDERAL and election.state:
            if user.state_of_residence.value != election.state.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": False,
                        "data": None,
                        "error": f"Only residents of {election.state.value} can vote in this election",
                        "message": "Vote failed"
                    }
                )
        
        # Check if user already voted for this position (using anonymous ID)
        anonymous_id = crypto_service.generate_anonymous_voter_id(user.id, election_id, position_id)
        existing_vote = db.query(EncryptedVote).filter(
            EncryptedVote.anonymous_voter_id == anonymous_id,
            EncryptedVote.election_id == election_id,
            EncryptedVote.position_id == position_id
        ).first()
        
        if existing_vote:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": False,
                    "data": None,
                    "error": f"You have already voted for {position.title}",
                    "message": "Vote failed"
                }
            )
        
        # Encrypt the vote
        encrypted_components = encrypt_vote(user.id, candidate_id, election_id, position_id)
        
        # Create encrypted vote record
        encrypted_vote = EncryptedVote(
            anonymous_voter_id=encrypted_components["anonymous_voter_id"],
            election_id=election_id,
            position_id=position_id,
            candidate_id=candidate_id,
            encrypted_vote_data=encrypted_components["encrypted_vote_data"],
            vote_hash=encrypted_components["vote_hash"],
            vote_receipt=encrypted_components["vote_receipt"],
            receipt_hash=encrypted_components["receipt_hash"],
            commitment_hash=encrypted_components["commitment_hash"],
            cast_at=encrypted_components["timestamp"]
        )
        
        db.add(encrypted_vote)
        db.flush()
        
        # Store commitment factor separately
        commitment = VoteCommitment(
            vote_hash=encrypted_components["vote_hash"],
            commitment_factor=encrypted_components["commitment_factor"]
        )
        db.add(commitment)
        
        # Create audit log
        audit_log = SecureVotingService._create_audit_log(
            db=db,
            action="SECURE_VOTE_CAST",
            user_id=user.id,
            details={
                "election_id": election_id,
                "position_id": position_id,
                "vote_receipt": encrypted_components["vote_receipt"],
                "anonymous_voter_id": anonymous_id[:16] + "...",
            },
            ip_address=ip_address
        )
        
        db.commit()
        db.refresh(encrypted_vote)
        
        return {
            "success": True,
            "vote_receipt": encrypted_components["vote_receipt"],
            "message": f"Vote cast successfully for {position.title}! Save your receipt to verify your vote.",
            "cast_at": encrypted_vote.cast_at.isoformat(),
            "election_name": election.title,
            "position_title": position.title
        }
    
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