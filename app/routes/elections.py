from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from sqlalchemy import func
from datetime import datetime, timezone

from app.models.database import get_db
from app.models.models import Election, Position, Candidate, Vote, User, State, ElectionType, PoliticalParty
from app.schemas.schemas import (
    ElectionCreate, ElectionResponse, ElectionWithPositions,
    PositionCreate, PositionResponse, 
    CandidateCreate, CandidateResponse,
    VoteRequest, VoteResponse, StandardResponse, PoliticalPartyResponse,
    CandidateWithVotes, PositionWithCandidates
)
from app.core.roles import get_current_admin
from app.routes.auth import get_current_active_user
from app.services.secure_voting_service import SecureVotingService
from app.core.roles import get_current_super_admin
 
from app.services.secure_voting_service import SecureVotingService
from app.core.roles import get_current_super_admin

router = APIRouter()

# === PUBLIC ELECTION ENDPOINTS ===

@router.get("/elections/active", response_model=StandardResponse[List[ElectionResponse]])
async def get_active_elections(db: Session = Depends(get_db)):
    """Get all active elections (Public)"""
    try:
        elections = db.query(Election).filter(Election.is_active == True).all()
        elections_response = [ElectionResponse.model_validate(election) for election in elections]
        
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

# @router.get("/elections/{election_id}", response_model=StandardResponse[ElectionWithPositions])
# async def get_election_details(
#     election_id: int,
#     db: Session = Depends(get_db)
# ):
#     """Get election details with positions and candidates (Public)"""
#     try:
#         election = db.query(Election).filter(Election.id == election_id).first()
#         if not election:
#             return StandardResponse[ElectionWithPositions](
#                 status=False,
#                 data=None,
#                 error="Election not found",
#                 message="Election retrieval failed"
#             )
        
#         # Get positions with candidates and vote counts
#         positions = db.query(Position).filter(Position.election_id == election_id).all()
        
#         positions_with_candidates = []
#         for position in positions:
#             candidates = db.query(Candidate).filter(Candidate.position_id == position.id).all()
            
#             candidates_with_votes = []
#             for candidate in candidates:
#                 vote_count = db.query(Vote).filter(Vote.candidate_id == candidate.id).count()
#                 candidate_data = CandidateWithVotes.model_validate(candidate)
#                 candidate_data.votes_count = vote_count
#                 candidates_with_votes.append(candidate_data)
            
#             position_data = PositionWithCandidates.model_validate(position)
#             position_data.candidates = candidates_with_votes
#             positions_with_candidates.append(position_data)
        
#         total_votes = db.query(Vote).filter(Vote.election_id == election_id).count()
        
#         election_data = ElectionWithPositions.model_validate(election)
#         election_data.positions = positions_with_candidates
#         election_data.total_votes = total_votes
        
#         return StandardResponse[ElectionWithPositions](
#             status=True,
#             data=election_data,
#             error=None,
#             message="Election details retrieved successfully"
#         )
        
#     except Exception as e:
#         return StandardResponse[ElectionWithPositions](
#             status=False,
#             data=None,
#             error=str(e),
#             message="Error retrieving election details"
#         )

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
        
        # Get positions with candidates and vote counts
        positions = db.query(Position).filter(Position.election_id == election_id).all()
        
        positions_with_candidates = []
        for position in positions:
            candidates = db.query(Candidate).filter(Candidate.position_id == position.id).all()
            
            candidates_with_votes = []
            for candidate in candidates:
                # Skip candidates with missing user
                if not candidate.user:
                    print(f"⚠️  Warning: Candidate {candidate.id} has no associated user")
                    continue
                
                vote_count = db.query(Vote).filter(Vote.candidate_id == candidate.id).count()
                
                # Manually construct candidate data
                candidate_data = CandidateWithVotes(
                    id=candidate.id,
                    user_id=candidate.user_id,
                    name=candidate.user.full_name,  # Get name from user relationship
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
            
            # Manually construct position data
            position_data = PositionWithCandidates(
                id=position.id,
                title=position.title,
                description=position.description,
                election_id=position.election_id,
                candidates=candidates_with_votes
            )
            positions_with_candidates.append(position_data)
        
        total_votes = db.query(Vote).filter(Vote.election_id == election_id).count()
        
        # Manually construct election data
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
# === VOTING ENDPOINTS (Authenticated Users) ===

@router.post("/elections/{election_id}/vote", response_model=StandardResponse[VoteResponse])
async def cast_vote(
    election_id: int,
    vote_data: VoteRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Cast a vote in an election"""
    try:
        # Check if election exists and is active
        election = db.query(Election).filter(
            Election.id == election_id,
            Election.is_active == True
        ).first()
        
        if not election:
            return StandardResponse[VoteResponse](
                status=False,
                data=None,
                error="Election not found or not active",
                message="Vote failed"
            )
        
        # Check if user has already voted in this election
        existing_vote = db.query(Vote).filter(
            Vote.user_id == current_user.id,
            Vote.election_id == election_id
        ).first()
        
        if existing_vote:
            return StandardResponse[VoteResponse](
                status=False,
                data=None,
                error="You have already voted in this election",
                message="Vote failed"
            )
        
        # Check if candidate exists and belongs to this election
        candidate = db.query(Candidate).join(Position).filter(
            Candidate.id == vote_data.candidate_id,
            Position.election_id == election_id
        ).first()
        
        if not candidate:
            return StandardResponse[VoteResponse](
                status=False,
                data=None,
                error="Candidate not found in this election",
                message="Vote failed"
            )
        
        # Check state eligibility (for state/local elections)
        if election.election_type != ElectionType.FEDERAL and election.state:
            if current_user.state_of_residence != election.state:
                return StandardResponse[VoteResponse](
                    status=False,
                    data=None,
                    error=f"Only residents of {election.state.value} can vote in this election",
                    message="Vote failed"
                )
        
        # Create vote (encrypted_vote is placeholder for now)
        vote = Vote(
            user_id=current_user.id,
            candidate_id=vote_data.candidate_id,
            election_id=election_id,
            encrypted_vote=f"encrypted_{current_user.id}_{vote_data.candidate_id}"  # Placeholder
        )
        
        db.add(vote)
        db.commit()
        db.refresh(vote)
        
        vote_response = VoteResponse(
            vote_id=vote.id,
            message="Vote cast successfully"
        )
        
        return StandardResponse[VoteResponse](
            status=True,
            data=vote_response,
            error=None,
            message="Vote cast successfully"
        )
        
    except Exception as e:
        db.rollback()
        return StandardResponse[VoteResponse](
            status=False,
            data=None,
            error=str(e),
            message="Error casting vote"
        )

@router.get("/elections/{election_id}/my-vote", response_model=StandardResponse[dict])
async def get_my_vote(
    election_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Check if user has voted in an election"""
    try:
        vote = db.query(Vote).filter(
            Vote.user_id == current_user.id,
            Vote.election_id == election_id
        ).first()
        
        has_voted = vote is not None
        
        return StandardResponse[dict](
            status=True,
            data={
                "has_voted": has_voted,
                "voted_at": vote.created_at if vote else None
            },
            error=None,
            message="Vote status retrieved successfully"
        )
        
    except Exception as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Error retrieving vote status"
        )

# === ADMIN ELECTION MANAGEMENT ===

# @router.post("/elections", response_model=StandardResponse[ElectionResponse])
# async def create_election(
#     election_data: ElectionCreate,
#     current_user: User = Depends(get_current_admin),
#     db: Session = Depends(get_db)
# ):
#     """Create a new election (Admin only)"""
#     try:
#         # Validate state requirement for state/local elections
#         if election_data.election_type in [ElectionType.STATE, ElectionType.LOCAL]:
#             if not election_data.state:
#                 return StandardResponse[ElectionResponse](
#                     status=False,
#                     data=None,
#                     error="State is required for state and local elections",
#                     message="Election creation failed"
#                 )
        
#         election = Election(**election_data.model_dump())
        
#         db.add(election)
#         db.commit()
#         db.refresh(election)
        
#         election_response = ElectionResponse.model_validate(election)
        
#         return StandardResponse[ElectionResponse](
#             status=True,
#             data=election_response,
#             error=None,
#             message="Election created successfully"
#         )
        
#     except Exception as e:
#         db.rollback()
#         return StandardResponse[ElectionResponse](
#             status=False,
#             data=None,
#             error=str(e),
#             message="Error creating election"
#         )

# @router.post("/positions", response_model=StandardResponse[PositionResponse])
# async def create_position(
#     position_data: PositionCreate,
#     current_user: User = Depends(get_current_admin),
#     db: Session = Depends(get_db)
# ):
#     """Create a new position (Admin only)"""
#     try:
#         position = Position(**position_data.model_dump())
        
#         db.add(position)
#         db.commit()
#         db.refresh(position)
        
#         position_response = PositionResponse.model_validate(position)
        
#         return StandardResponse[PositionResponse](
#             status=True,
#             data=position_response,
#             error=None,
#             message="Position created successfully"
#         )
        
#     except Exception as e:
#         db.rollback()
#         return StandardResponse[PositionResponse](
#             status=False,
#             data=None,
#             error=str(e),
#             message="Error creating position"
#         )


@router.get("/elections/{election_id}/results", response_model=StandardResponse[dict])
async def get_election_results(
    election_id: int,
    db: Session = Depends(get_db)
):
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
        
        # Get all votes for this election
        votes = db.query(Vote).filter(Vote.election_id == election_id).all()
        total_votes = len(votes)
        
        # Get all candidates in this election with their parties
        candidates = db.query(Candidate).join(Position).filter(
            Position.election_id == election_id
        ).options(joinedload(Candidate.party)).all()
        
        # Calculate results by party
        party_results = {}
        for candidate in candidates:
            candidate_votes = db.query(Vote).filter(Vote.candidate_id == candidate.id).count()
            
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
            
            party_results[party_id]["total_votes"] += candidate_votes
            party_results[party_id]["candidates"].append({
                "candidate": candidate,
                "votes": candidate_votes
            })
        
        # Convert to response format
        results_data = {
            "election": ElectionResponse.model_validate(election),
            "total_votes": total_votes,
            "party_results": [
                {
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
                    "candidates": [
                        {
                            "candidate": CandidateResponse.model_validate(candidate_data["candidate"]),
                            "votes": candidate_data["votes"]
                        }
                        for candidate_data in party_data["candidates"]
                    ]
                }
                for party_data in party_results.values()
            ]
        }
        
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
# Add these routes to your existing router

@router.post("/elections/{election_id}/positions/{position_id}/vote-secure", 
             response_model=StandardResponse[dict])
async def cast_secure_vote(
    request: Request,
    election_id: int,
    position_id: int,
    vote_data: VoteRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Cast an encrypted, anonymous vote for a specific position
    Returns a vote receipt that the voter can use to verify their vote
    """
    try:
        # Get IP address
        from fastapi import Request
        ip_address = request.client.host if request.client else None
        
        result = SecureVotingService.cast_encrypted_vote(
            db=db,
            user=current_user,
            election_id=election_id,
            position_id=position_id,
            candidate_id=vote_data.candidate_id,
            ip_address=ip_address
        )
        
        return StandardResponse[dict](
            status=True,
            data=result,
            error=None,
            message=result["message"]
        )
    
    except HTTPException as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=e.detail.get("error") if isinstance(e.detail, dict) else str(e.detail),
            message="Failed to cast vote"
        )
    except Exception as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Failed to cast vote"
        )


@router.post("/vote/verify-receipt", response_model=StandardResponse[dict])
async def verify_vote_receipt(
    request: Request,
    vote_receipt: str = Query(..., description="Vote receipt to verify"),
    db: Session = Depends(get_db)
):
    """
    Verify a vote receipt (public endpoint - no authentication required)
    
    Allows voters to confirm their vote was counted without revealing their identity
    """
    try:
        # Get IP address
        ip_address = request.client.host if request.client else None
        
        result = SecureVotingService.verify_vote_receipt(
            db=db,
            vote_receipt=vote_receipt,
            ip_address=ip_address
        )
        
        return StandardResponse[dict](
            status=True,
            data=result,
            error=None,
            message=result["message"]
        )
    
    except HTTPException as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=e.detail.get("error") if isinstance(e.detail, dict) else str(e.detail),
            message="Verification failed"
        )
    except Exception as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Failed to verify receipt"
        )


@router.post("/elections/{election_id}/tally-secure", response_model=StandardResponse[dict])
async def tally_election_secure(
    election_id: int,
    current_user: User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    """
    Tally votes for an election using encrypted votes (Super Admin only)
    
    Decrypts votes, verifies integrity, and counts votes for all positions
    """
    try:
        result = SecureVotingService.tally_election_votes(
            db=db,
            admin_user=current_user,
            election_id=election_id
        )
        
        return StandardResponse[dict](
            status=True,
            data=result,
            error=None,
            message=result["message"]
        )
    
    except HTTPException as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=e.detail.get("error") if isinstance(e.detail, dict) else str(e.detail),
            message="Tally failed"
        )
    except Exception as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Failed to tally votes"
        )


@router.get("/elections/{election_id}/my-voting-status", response_model=StandardResponse[dict])
async def get_my_voting_status(
    election_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's voting status for all positions in an election
    Shows which positions they've voted for and their receipts
    """
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
    """
    Check if current user has already voted for a specific position
    """
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
    """
    Verify entire audit trail integrity (Super Admin only)
    
    Checks blockchain-style hash chain for tampering
    """
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
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Get secure election statistics (Admin only)
    Shows encrypted vote counts without revealing individual votes
    """
    try:
        from app.models.models import EncryptedVote, Position
        
        election = db.query(Election).filter(Election.id == election_id).first()
        if not election:
            return StandardResponse[dict](
                status=False,
                data=None,
                error="Election not found",
                message="Statistics retrieval failed"
            )
        
        # Get all positions
        positions = db.query(Position).filter(Position.election_id == election_id).all()
        
        position_stats = []
        total_secure_votes = 0
        
        for position in positions:
            vote_count = db.query(EncryptedVote).filter(
                EncryptedVote.election_id == election_id,
                EncryptedVote.position_id == position.id
            ).count()
            
            verified_count = db.query(EncryptedVote).filter(
                EncryptedVote.election_id == election_id,
                EncryptedVote.position_id == position.id,
                EncryptedVote.verified == True
            ).count()
            
            position_stats.append({
                "position_id": position.id,
                "position_title": position.title,
                "total_votes": vote_count,
                "verified_votes": verified_count,
                "pending_votes": vote_count - verified_count
            })
            
            total_secure_votes += vote_count
        
        # Get verification attempts
        vote_receipts = db.query(EncryptedVote.vote_receipt).filter(
            EncryptedVote.election_id == election_id
        ).all()
        receipt_list = [r[0] for r in vote_receipts]
        
        from app.models.models import VoteVerification
        verification_count = db.query(VoteVerification).filter(
            VoteVerification.vote_receipt.in_(receipt_list)
        ).count() if receipt_list else 0
        
        return StandardResponse[dict](
            status=True,
            data={
                "election_id": election_id,
                "election_name": election.title,
                "total_secure_votes": total_secure_votes,
                "verification_attempts": verification_count,
                "position_statistics": position_stats,
                "election_status": "active" if datetime.utcnow() < election.end_date else "ended"
            },
            error=None,
            message="Statistics retrieved successfully"
        )
    
    except Exception as e:
        return StandardResponse[dict](
            status=False,
            data=None,
            error=str(e),
            message="Failed to get statistics"
        )
    

# ================================
# GET UPCOMING ELECTIONS
# ================================
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
        status="success",
        message="Upcoming elections retrieved successfully",
        data=elections
    )


# ================================
# GET PAST ELECTIONS
# ================================
@router.get("/past", response_model=StandardResponse)
def get_past_elections(db: Session = Depends(get_db)):

    now = datetime.now(timezone.utc)

    elections = (
        db.query(Election)
        .filter(Election.end_date < now)
        .order_by(Election.end_date.desc())
        .all()
    )

    return StandardResponse(
        status="success",
        message="Past elections retrieved successfully",
        data=elections
    )