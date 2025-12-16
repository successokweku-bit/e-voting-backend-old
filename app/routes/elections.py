from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Dict, Any
from sqlalchemy import func, or_
from datetime import datetime, timezone

from app.models.database import get_db
from app.models.models import (
    Election, Position, Candidate, Vote, User, State, ElectionType, 
    PoliticalParty, EncryptedVote, VoteVerification
)
from app.schemas.schemas import (
    ElectionCreate, ElectionResponse, ElectionWithPositions,
    PositionCreate, PositionResponse, 
    CandidateCreate, CandidateResponse, CandidateElectionResponse,
    VoteRequest, VoteResponse, StandardResponse, PoliticalPartyResponse,
    CandidateWithVotes, PositionWithCandidates, PartyResponse, SecureVoteResult
)

from app.core.roles import get_current_admin
from app.routes.auth import get_current_active_user
from app.services.secure_voting_service import SecureVotingService
from app.core.roles import get_current_super_admin
from app.services.email_service import email_service

def get_current_utc_time():
    """Get current UTC time as timezone-aware datetime"""
    return datetime.now(timezone.utc)

router = APIRouter()

# === EXISTING ENDPOINTS (keeping them as they are) ===

# @router.get("/elections/active", response_model=StandardResponse[List[ElectionResponse]])
# async def get_active_elections(db: Session = Depends(get_db)):
#     """Get all active elections (Public)"""
#     try:
#         elections = db.query(Election).filter(Election.is_active == True).all()
#         elections_response = [ElectionResponse.model_validate(election) for election in elections]
        
#         return StandardResponse[List[ElectionResponse]](
#             status=True,
#             data=elections_response,
#             error=None,
#             message=f"Found {len(elections_response)} active elections"
#         )
        
#     except Exception as e:
#         return StandardResponse[List[ElectionResponse]](
#             status=False,
#             data=None,
#             error=str(e),
#             message="Error retrieving active elections"
#         )

@router.get("/elections/active", response_model=StandardResponse[List[ElectionResponse]])
async def get_active_elections(db: Session = Depends(get_db)):
    """Get all active elections (Public)"""
    try:
        now = datetime.utcnow()

        elections = (
            db.query(Election)
            .filter(
                Election.is_active == True,
                Election.start_date <= now,
                or_(
                    Election.end_date == None,
                    Election.end_date >= now
                )
            )
            .all()
        )

        elections_response = [
            ElectionResponse.model_validate(election)
            for election in elections
        ]

        return StandardResponse[List[ElectionResponse]](
            status=True,
            data=elections_response,
            error=None,
            message=f"Found {len(elections_response)} active elections"
        )

    except Exception as e:
        return StandardResponse[List[ElectionResponse]](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving active elections"
        )
    
@router.get("/elections/{election_id}", response_model=StandardResponse[ElectionWithPositions])
async def get_election_details(
    election_id: int,
    db: Session = Depends(get_db)
):
    """Get election details with positions and candidates (Public)"""
    try:
        election = db.query(Election).filter(Election.id == election_id).first()
        if not election:
            return StandardResponse[ElectionWithPositions](
                status=False,
                data=None,
                error="Election not found",
                message="Election retrieval failed"
            )
        
        positions = db.query(Position).filter(Position.election_id == election_id).all()
        
        positions_with_candidates = []
        for position in positions:
            candidates = db.query(Candidate).filter(Candidate.position_id == position.id).all()
            
            candidates_with_votes = []
            for candidate in candidates:
                if not candidate.user:
                    print(f"⚠️  Warning: Candidate {candidate.id} has no associated user")
                    continue
                
                vote_count = db.query(Vote).filter(Vote.candidate_id == candidate.id).count()
                
                candidate_data = CandidateWithVotes(
                    id=candidate.id,
                    user_id=candidate.user_id,
                    name=candidate.user.full_name,
                    position_id=candidate.position_id,
                    party_id=candidate.party_id,
                    bio=candidate.bio,
                    manifestos=candidate.manifestos if candidate.manifestos else [],
                    election=Election(
                        id=election.id,
                        title=election.title,
                        description=election.description,
                        election_type=election.election_type,
                        state=election.state,
                        start_date=election.start_date,
                        end_date=election.end_date
                    ) if election else None,
                    votes_count=vote_count
                )
                candidates_with_votes.append(candidate_data)
            
            position_data = PositionWithCandidates(
                id=position.id,
                title=position.title,
                description=position.description,
                election_id=position.election_id,
                candidates=candidates_with_votes
            )
            positions_with_candidates.append(position_data)
        
        total_votes = db.query(Vote).filter(Vote.election_id == election_id).count()
        
        election_data = ElectionWithPositions(
            id=election.id,
            title=election.title,
            description=election.description,
            election_type=election.election_type,
            state=election.state,
            is_active=election.is_active,
            start_date=election.start_date,
            end_date=election.end_date,
            created_at=election.created_at,
            positions=positions_with_candidates,
            total_votes=total_votes
        )
        
        return StandardResponse[ElectionWithPositions](
            status=True,
            data=election_data,
            error=None,
            message="Election details retrieved successfully"
        )
        
    except Exception as e:
        print(f"❌ Error retrieving election details: {str(e)}")
        import traceback
        traceback.print_exc()
        return StandardResponse[ElectionWithPositions](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving election details"
        )

@router.get(
    "/elections/{election_id}/positions/{position_id}/candidates",
    response_model=StandardResponse[List[CandidateElectionResponse]]
)
async def get_candidates_for_position(
    election_id: int,
    position_id: int,
    db: Session = Depends(get_db)
):
    try:
        candidates = (
            db.query(Candidate)
            .filter(
                Candidate.election_id == election_id,
                Candidate.position_id == position_id,
            )
            .all()
        )

        result = []
        for c in candidates:
            election_info = Election(
                id=c.election.id,
                title=c.election.title,
                description=c.election.description,
                election_type=c.election.election_type.value if c.election.election_type else None,
                state=c.election.state.value if c.election.state else None,
                start_date=c.election.start_date,
                end_date=c.election.end_date,
            )

            party_info = None
            if c.party:
                party_info = PartyResponse(
                    id=c.party.id,
                    name=c.party.name,
                    description=c.party.description,
                    logo_url=c.party.logo_url
                )

            result.append(
                CandidateElectionResponse(
                    id=c.id,
                    user_id=c.user_id,
                    name=c.user.full_name,
                    position_id=c.position_id,
                    bio=c.bio,
                    manifestos=c.manifestos,
                    party=party_info,          
                    election=election_info
                )
            )

        return StandardResponse[List[CandidateElectionResponse]](
            status=True,
            data=result,
            error=None,
            message=f"Retrieved {len(result)} candidates"
        )

    except Exception as e:
        return StandardResponse[List[CandidateElectionResponse]](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving candidates"
        )

@router.get("/elections/{election_id}/results", response_model=StandardResponse[dict])
async def get_election_results(election_id: int, db: Session = Depends(get_db)):
    """Get detailed election results with party information (Public)"""
    try:
        election = db.query(Election).filter(Election.id == election_id).first()
        if not election:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Election not found",
                message="Results retrieval failed"
            )

        candidates = db.query(Candidate).join(Position).filter(
            Position.election_id == election_id
        ).options(
            joinedload(Candidate.user),
            joinedload(Candidate.party),
            joinedload(Candidate.election)
        ).all()

        total_votes = 0
        party_results = {}

        for candidate in candidates:
            vote_count = db.query(EncryptedVote).filter(EncryptedVote.candidate_id == candidate.id).count()
            total_votes += vote_count

            party_id = candidate.party.id if candidate.party else 0
            party_name = candidate.party.name if candidate.party else "Independent"
            party_acronym = candidate.party.acronym if candidate.party else "IND"

            if party_id not in party_results:
                party_results[party_id] = {
                    "party": candidate.party,
                    "total_votes": 0,
                    "candidates": [],
                    "party_name": party_name,
                    "party_acronym": party_acronym
                }

            party_results[party_id]["total_votes"] += vote_count

            candidate_data = CandidateResponse(
                id=candidate.id,
                user_id=candidate.user_id,
                name=candidate.user.full_name if candidate.user else "Unknown",
                position_id=candidate.position_id,
                party_id=candidate.party_id,
                bio=candidate.bio,
                manifestos=candidate.manifestos,
                election=Election(
                    id=election.id,
                    title=election.title,
                    description=election.description,
                    election_type=election.election_type.value,
                    state=election.state.value if election.state else None,
                    start_date=election.start_date,
                    end_date=election.end_date
                )
            )
            party_results[party_id]["candidates"].append({
                "candidate": candidate_data,
                "votes": vote_count
            })

        results_data = {
            "election": ElectionResponse.model_validate(election),
            "total_votes": total_votes,
            "party_results": []
        }

        for party_data in party_results.values():
            results_data["party_results"].append({
                "party": PoliticalPartyResponse.model_validate(party_data["party"]) if party_data["party"] else {
                    "id": 0,
                    "name": party_data["party_name"],
                    "acronym": party_data["party_acronym"],
                    "logo_url": None,
                    "description": "Independent candidate",
                    "founded_date": None,
                    "created_at": datetime.utcnow()
                },
                "total_votes": party_data["total_votes"],
                "percentage": (party_data["total_votes"] / total_votes * 100) if total_votes > 0 else 0,
                "candidates": party_data["candidates"]
            })

        return StandardResponse[dict](
            status=True,
            data=results_data,
            error=None,
            message="Election results retrieved successfully"
        )

    except Exception as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving election results"
        )
        
@router.get("/parties", response_model=StandardResponse[List[PoliticalPartyResponse]])
async def get_all_parties_public(db: Session = Depends(get_db)):
    """Get all political parties (Public)"""
    try:
        parties = db.query(PoliticalParty).all()
        parties_response = [PoliticalPartyResponse.model_validate(party) for party in parties]
        
        return StandardResponse[List[PoliticalPartyResponse]](
            status=True,
            data=parties_response,
            error=None,
            message=f"Retrieved {len(parties_response)} political parties"
        )
        
    except Exception as e:
        return StandardResponse[List[PoliticalPartyResponse]](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving political parties"
        )

# ==================== SECURE VOTING ENDPOINTS ====================

@router.post(
    "/elections/{election_id}/positions/{position_id}/vote-secure",
    response_model=StandardResponse[SecureVoteResult]
)
async def cast_secure_vote(
    request: Request,
    election_id: int,
    position_id: int,
    candidate_id: int = Form(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Cast a secure encrypted vote and automatically send receipt via email
    """
    try:
        ip_address = request.client.host if request.client else None

        # Cast the vote
        result = SecureVotingService.cast_encrypted_vote(
            db=db,
            user=current_user,
            election_id=election_id,
            position_id=position_id,
            candidate_id=candidate_id,
            ip_address=ip_address
        )

        # 🆕 Send email with vote receipt
        try:
            email_sent = email_service.send_vote_receipt_email(
                user_email=current_user.email,
                user_name=current_user.full_name,
                vote_receipt=result["vote_receipt"],
                election_name=result["election"],
                position_name=result["position"],
                candidate_name=result["candidate"],
                timestamp=result["timestamp"]
            )
            
            if email_sent:
                result["email_sent"] = True
                result["message"] = "Vote cast successfully! Receipt sent to your email."
            else:
                result["email_sent"] = False
                result["message"] = "Vote cast successfully! (Email delivery failed, but your receipt is displayed below)"
                
        except Exception as email_error:
            print(f"⚠️ Email sending failed: {str(email_error)}")
            result["email_sent"] = False
            result["message"] = "Vote cast successfully! (Email delivery failed, but your receipt is displayed below)"

        return StandardResponse(
            status=True,
            data=SecureVoteResult.model_validate(result),
            message=result["message"]
        )

    except HTTPException as e:
        return StandardResponse(
            status=False,
            error=e.detail.get("error") if isinstance(e.detail, dict) else str(e.detail),
            message="Failed to cast vote"
        )

    except Exception as e:
        return StandardResponse(
            status=False,
            error=str(e),
            message="Failed to cast vote"
        )

@router.get("/vote/details-by-receipt", response_model=StandardResponse[dict])
async def get_vote_details_by_receipt(
    vote_receipt: str = Query(..., description="Vote receipt code"),
    db: Session = Depends(get_db)
):
    """
    🆕 Get vote details using receipt code (Public - no authentication required)
    
    This allows voters to look up their vote information using just their receipt
    """
    try:
        # Find the encrypted vote by receipt
        encrypted_vote = db.query(EncryptedVote).filter(
            EncryptedVote.vote_receipt == vote_receipt
        ).first()

        if not encrypted_vote:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Vote receipt not found",
                message="Invalid receipt code"
            )

        # Get related data
        election = db.query(Election).filter(
            Election.id == encrypted_vote.election_id
        ).first()

        position = db.query(Position).filter(
            Position.id == encrypted_vote.position_id
        ).first()

        candidate = db.query(Candidate).options(
            joinedload(Candidate.user),
            joinedload(Candidate.party)
        ).filter(
            Candidate.id == encrypted_vote.candidate_id
        ).first()

        # Build response
        vote_details = {
            "vote_receipt": vote_receipt,
            "election": {
                "id": election.id,
                "title": election.title,
                "description": election.description,
                "election_type": election.election_type.value if election.election_type else None,
                "state": election.state.value if election.state else None
            } if election else None,
            "position": {
                "id": position.id,
                "title": position.title,
                "description": position.description
            } if position else None,
            "candidate": {
                "id": candidate.id,
                "name": candidate.user.full_name if candidate.user else "Unknown",
                "bio": candidate.bio,
                "party": {
                    "name": candidate.party.name,
                    "acronym": candidate.party.acronym,
                    "logo_url": candidate.party.logo_url
                } if candidate.party else None
            } if candidate else None,
            "cast_at": encrypted_vote.cast_at.isoformat() if encrypted_vote.cast_at else None,
            "verified": encrypted_vote.verified,
            "tallied": encrypted_vote.tallied,
            "vote_hash": encrypted_vote.vote_hash[:16] + "..." if encrypted_vote.vote_hash else None,
            "status": "Verified and Counted" if encrypted_vote.tallied else "Pending Verification"
        }

        return StandardResponse[dict](
            status=True,
            data=vote_details,
            error=None,
            message="Vote details retrieved successfully"
        )

    except Exception as e:
        print(f"❌ Error retrieving vote details: {str(e)}")
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Failed to retrieve vote details"
        )

@router.get("/my-votes", response_model=StandardResponse[dict])
async def get_my_votes(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    🆕 Get all votes cast by the current user across all elections
    
    Returns complete details of all elections, positions, and candidates voted for
    """
    try:
        # Get all encrypted votes for this user by checking anonymous voter IDs
        # We need to reconstruct the anonymous IDs for all possible combinations
        
        # Get all elections
        elections = db.query(Election).all()
        
        my_votes = []
        
        for election in elections:
            # Get all positions in this election
            positions = db.query(Position).filter(
                Position.election_id == election.id
            ).all()
            
            for position in positions:
                # Generate anonymous voter ID for this user, election, and position
                anonymous_voter_id = SecureVotingService._generate_anonymous_id(
                    current_user.id,
                    election.id,
                    position.id
                )
                
                # Check if there's a vote with this anonymous ID
                encrypted_vote = db.query(EncryptedVote).filter(
                    EncryptedVote.anonymous_voter_id == anonymous_voter_id,
                    EncryptedVote.election_id == election.id,
                    EncryptedVote.position_id == position.id
                ).first()
                
                if encrypted_vote:
                    # Get candidate details
                    candidate = db.query(Candidate).options(
                        joinedload(Candidate.user),
                        joinedload(Candidate.party)
                    ).filter(
                        Candidate.id == encrypted_vote.candidate_id
                    ).first()
                    
                    vote_info = {
                        "vote_id": encrypted_vote.id,
                        "vote_receipt": encrypted_vote.vote_receipt,
                        "election": {
                            "id": election.id,
                            "title": election.title,
                            "description": election.description,
                            "election_type": election.election_type.value if election.election_type else None,
                            "state": election.state.value if election.state else None,
                            "start_date": election.start_date.isoformat() if election.start_date else None,
                            "end_date": election.end_date.isoformat() if election.end_date else None,
                            "is_active": election.is_active
                        },
                        "position": {
                            "id": position.id,
                            "title": position.title,
                            "description": position.description
                        },
                        "candidate": {
                            "id": candidate.id,
                            "name": candidate.user.full_name if candidate.user else "Unknown",
                            "bio": candidate.bio,
                            "manifestos": candidate.manifestos,
                            "party": {
                                "id": candidate.party.id,
                                "name": candidate.party.name,
                                "acronym": candidate.party.acronym,
                                "logo_url": candidate.party.logo_url
                            } if candidate.party else None
                        } if candidate else None,
                        "cast_at": encrypted_vote.cast_at.isoformat() if encrypted_vote.cast_at else None,
                        "verified": encrypted_vote.verified,
                        "tallied": encrypted_vote.tallied,
                        "status": "Verified and Counted" if encrypted_vote.tallied else "Pending Verification"
                    }
                    
                    my_votes.append(vote_info)
        
        # Group votes by election
        votes_by_election = {}
        for vote in my_votes:
            election_id = vote["election"]["id"]
            if election_id not in votes_by_election:
                votes_by_election[election_id] = {
                    "election": vote["election"],
                    "votes": []
                }
            votes_by_election[election_id]["votes"].append({
                "vote_receipt": vote["vote_receipt"],
                "position": vote["position"],
                "candidate": vote["candidate"],
                "cast_at": vote["cast_at"],
                "verified": vote["verified"],
                "status": vote["status"]
            })
        
        result = {
            "total_votes": len(my_votes),
            "total_elections_participated": len(votes_by_election),
            "votes_by_election": list(votes_by_election.values()),
            "all_votes": my_votes  # Also include flat list for easier access
        }

        return StandardResponse[dict](
            status=True,
            data=result,
            error=None,
            message=f"Retrieved {len(my_votes)} votes across {len(votes_by_election)} elections"
        )

    except Exception as e:
        print(f"❌ Error retrieving user votes: {str(e)}")
        import traceback
        traceback.print_exc()
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Failed to retrieve your votes"
        )

# Other existing secure voting endpoints...

@router.post("/elections/{election_id}/tally-secure", response_model=StandardResponse[dict])
async def tally_secure_votes(
    election_id: int, 
    current_user: User = Depends(get_current_active_user), 
    db: Session = Depends(get_db)
):
    result = SecureVotingService.tally_election_votes(db, current_user, election_id)
    return StandardResponse(status=True, data=result, error=None, message=result["message"])

@router.get("/elections/{election_id}/my-voting-status", response_model=StandardResponse[dict])
async def get_my_voting_status(
    election_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's voting status for all positions in an election"""
    try:
        result = SecureVotingService.get_user_voting_status(
            db=db,
            user_id=current_user.id,
            election_id=election_id
        )
        
        return StandardResponse[dict](
            status=True,
            data=result,
            error=None,
            message="Voting status retrieved successfully"
        )
    
    except Exception as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Failed to get voting status"
        )

@router.get("/elections/{election_id}/positions/{position_id}/has-voted", 
            response_model=StandardResponse[dict])
async def check_position_voted(
    election_id: int,
    position_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Check if current user has already voted for a specific position"""
    try:
        has_voted = SecureVotingService.check_user_voted_for_position(
            db=db,
            user_id=current_user.id,
            election_id=election_id,
            position_id=position_id
        )
        
        return StandardResponse[dict](
            status=True,
            data={
                "has_voted": has_voted,
                "election_id": election_id,
                "position_id": position_id
            },
            error=None,
            message="Vote status checked"
        )
    
    except Exception as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Failed to check vote status"
        )

@router.get("/audit/verify", response_model=StandardResponse[dict])
async def verify_audit_trail(
    current_user: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    """Verify entire audit trail integrity (Super Admin only)"""
    try:
        result = SecureVotingService.verify_audit_trail(db=db)
        
        return StandardResponse[dict](
            status=True,
            data=result,
            error=None,
            message=result["message"]
        )
    
    except Exception as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Failed to verify audit trail"
        )

@router.get("/elections/{election_id}/secure-statistics", response_model=StandardResponse[dict])
async def get_secure_election_statistics(
    election_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get secure election statistics (Admin only)"""
    try:
        election = db.query(Election).filter(Election.id == election_id).first()
        if not election:
            return StandardResponse(
                status=False,
                data=None,
                error="Election not found",
                message="Statistics retrieval failed"
            )

        positions = db.query(Position).filter(
            Position.election_id == election_id
        ).all()

        position_stats = []
        total_secure_votes = 0

        for position in positions:
            total_votes = db.query(EncryptedVote).filter(
                EncryptedVote.election_id == election_id,
                EncryptedVote.position_id == position.id
            ).count()

            verified_votes = db.query(EncryptedVote).filter(
                EncryptedVote.election_id == election_id,
                EncryptedVote.position_id == position.id,
                EncryptedVote.verified.is_(True)
            ).count()

            position_stats.append({
                "position_id": position.id,
                "position_title": position.title,
                "total_votes": total_votes,
                "verified_votes": verified_votes,
                "pending_votes": total_votes - verified_votes
            })

            total_secure_votes += total_votes

        receipts = db.query(EncryptedVote.vote_receipt).filter(
            EncryptedVote.election_id == election_id
        ).all()

        receipt_list = [r[0] for r in receipts]

        verification_attempts = db.query(VoteVerification).filter(
            VoteVerification.vote_receipt.in_(receipt_list)
        ).count() if receipt_list else 0

        now_utc = datetime.now(timezone.utc)

        election_status = (
            "active"
            if election.start_date <= now_utc <= election.end_date
            else "ended"
        )

        return StandardResponse(
            status=True,
            data={
                "election_id": election.id,
                "election_name": election.title,
                "total_secure_votes": total_secure_votes,
                "verification_attempts": verification_attempts,
                "position_statistics": position_stats,
                "election_status": election_status
            },
            error=None,
            message="Statistics retrieved successfully"
        )

    except Exception as e:
        return StandardResponse(
            status=False,
            data=None,
            error=str(e),
            message="Failed to get statistics"
        )

@router.get("/upcoming", response_model=StandardResponse)
def get_upcoming_elections(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    elections = (
        db.query(Election)
        .filter(Election.start_date > now)
        .order_by(Election.start_date.asc())
        .all()
    )
    return StandardResponse(
        status=True,
        message="Upcoming elections retrieved successfully",
        data=elections
    )

@router.get("/past", response_model=StandardResponse[list[ElectionResponse]])
def get_past_elections(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    elections = (
        db.query(Election)
        .filter(Election.end_date < now)
        .order_by(Election.end_date.desc())
        .all()
    )
    return StandardResponse(
        status=True,
        message="Past elections retrieved successfully",
        data=[ElectionResponse.model_validate(e) for e in elections]
    )