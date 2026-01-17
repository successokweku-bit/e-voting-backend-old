from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Dict, Any
from sqlalchemy import func, or_
from datetime import datetime, timezone

from app.models.database import get_db
from app.models.models import (
    Election, ElectionStatus, Position, Candidate, Vote, User, State, ElectionType, 
    PoliticalParty, EncryptedVote, VoteVerification
)
from app.schemas.schemas import (
    ElectionCreate, ElectionResponse, ElectionWithPositions,
    PositionCreate, PositionResponse, 
    CandidateCreate, CandidateResponse, CandidateElectionResponse, VoteDetailsRequest,
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

# @router.get("/elections/active", response_model=StandardResponse[List[ElectionResponse]])
# async def get_active_elections(db: Session = Depends(get_db)):
#     """Get all active elections (Public)"""
#     try:
#         now = datetime.utcnow()

#         elections = (
#             db.query(Election)
#             .filter(
#                 Election.is_active == True,
#                 Election.start_date <= now,
#                 or_(
#                     Election.end_date == None,
#                     Election.end_date >= now
#                 )
#             )
#             .all()
#         )

#         elections_response = [
#             ElectionResponse.model_validate(election)
#             for election in elections
#         ]

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
        # 1. Use timezone-aware UTC for accurate comparison
        now = datetime.now(timezone.utc)

        # 2. Query for elections that are marked active and are within the date range
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

        # 3. Safe serialization helper (defined inside or outside the function)
        def get_val(attr):
            return attr.value if hasattr(attr, 'value') else attr

        elections_response = []
        for election in elections:
            # We manually construct the response or use model_validate 
            # while ensuring the Enum attributes are safe.
            # accessing 'election.status' here triggers your @property logic.
            
            data = {
                "id": election.id,
                "title": election.title,
                "description": election.description,
                "election_type": get_val(election.election_type),
                "state": get_val(election.state),
                "status": get_val(election.status), # This handles the @property
                "is_active": election.is_active,
                "start_date": election.start_date,
                "end_date": election.end_date,
                "created_at": election.created_at
            }
            elections_response.append(ElectionResponse(**data))

        return StandardResponse(
            status=True,
            data=elections_response,
            message=f"Found {len(elections_response)} active elections"
        )
    except Exception as e:
        # Logging the error is helpful for debugging
        print(f"Error in get_active_elections: {e}")
        return StandardResponse(
            status=False, 
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
        # Helper to handle Enum vs String serialization
        def safe_val(attr):
            return attr.value if hasattr(attr, 'value') else attr

        # 1. Use joinedload to fetch everything in one go for performance
        election = db.query(Election).options(
            joinedload(Election.positions).joinedload(Position.candidates).joinedload(Candidate.user),
            joinedload(Election.positions).joinedload(Position.candidates).joinedload(Candidate.party)
        ).filter(Election.id == election_id).first()
        
        if not election:
            return StandardResponse(
                status=False,
                error="Election not found",
                message="Election retrieval failed"
            )

        # 2. Map positions
        positions_with_candidates = []
        for position in election.positions:
            
            candidates_with_votes = []
            for candidate in position.candidates:
                if not candidate.user:
                    continue
                
                # Count votes from the secure table
                vote_count = db.query(EncryptedVote).filter(
                    EncryptedVote.candidate_id == candidate.id
                ).count()
                
                # Manual construction to avoid Enum crash inside nested CandidateWithVotes
                candidate_data = CandidateWithVotes(
                    id=candidate.id,
                    user_id=candidate.user_id,
                    name=candidate.user.full_name,
                    position_id=candidate.position_id,
                    party_id=candidate.party_id,
                    bio=candidate.bio,
                    manifestos=candidate.manifestos or [],
                    # Serialize election part safely
                    election=ElectionResponse(
                        id=election.id,
                        title=election.title,
                        description=election.description,
                        election_type=safe_val(election.election_type),
                        state=safe_val(election.state),
                        status=safe_val(election.status), # Accesses @property safely
                        is_active=election.is_active,
                        start_date=election.start_date,
                        end_date=election.end_date,
                        created_at=election.created_at
                    ),
                    votes_count=vote_count
                )
                candidates_with_votes.append(candidate_data)
            
            positions_with_candidates.append(PositionWithCandidates(
                id=position.id,
                title=position.title,
                description=position.description,
                election_id=position.election_id,
                candidates=candidates_with_votes
            ))
        
        # 3. Total votes
        total_votes = db.query(EncryptedVote).filter(
            EncryptedVote.election_id == election_id
        ).count()
        
        # 4. Construct final response safely
        election_data = ElectionWithPositions(
            id=election.id,
            title=election.title,
            description=election.description,
            election_type=safe_val(election.election_type),
            state=safe_val(election.state),
            status=safe_val(election.status), # Accesses @property safely
            is_active=election.is_active,
            start_date=election.start_date,
            end_date=election.end_date,
            created_at=election.created_at,
            positions=positions_with_candidates,
            total_votes=total_votes
        )
        
        return StandardResponse(
            status=True,
            data=election_data,
            message="Election details retrieved successfully"
        )
        
    except Exception as e:
        print(f" Error in get_election_details: {str(e)}")
        return StandardResponse(
            status=False,
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
        # Helper to handle Enum vs String serialization safely
        def safe_val(attr):
            return attr.value if hasattr(attr, 'value') else attr

        election = db.query(Election).filter(Election.id == election_id).first()
        if not election:
            return StandardResponse(
                status=False,
                error="Election not found",
                message="Results retrieval failed"
            )

        candidates = db.query(Candidate).join(Position).filter(
            Position.election_id == election_id
        ).options(
            joinedload(Candidate.user),
            joinedload(Candidate.party)
        ).all()

        total_votes = 0
        party_results = {}

        # Pre-validate election response to reuse status property
        election_serialized = ElectionResponse.model_validate(election)

        for candidate in candidates:
            # Count votes from secure table
            vote_count = db.query(EncryptedVote).filter(
                EncryptedVote.candidate_id == candidate.id
            ).count()
            total_votes += vote_count

            party_id = candidate.party.id if candidate.party else 0
            
            if party_id not in party_results:
                party_results[party_id] = {
                    "party_obj": candidate.party,
                    "total_votes": 0,
                    "candidates": [],
                    "fallback_name": candidate.party.name if candidate.party else "Independent",
                    "fallback_acronym": candidate.party.acronym if candidate.party else "IND"
                }

            party_results[party_id]["total_votes"] += vote_count

            # Safe Candidate serialization
            candidate_data = CandidateResponse(
                id=candidate.id,
                user_id=candidate.user_id,
                name=candidate.user.full_name if candidate.user else "Unknown",
                position_id=candidate.position_id,
                party_id=candidate.party_id,
                bio=candidate.bio,
                manifestos=candidate.manifestos or [],
                election=election_serialized # Reuse the pre-validated response
            )
            
            party_results[party_id]["candidates"].append({
                "candidate": candidate_data,
                "votes": vote_count
            })

        formatted_party_results = []
        for p_id, p_data in party_results.items():
            # Handle the Party serialization safely
            if p_data["party_obj"]:
                party_info = PoliticalPartyResponse.model_validate(p_data["party_obj"])
            else:
                party_info = {
                    "id": 0,
                    "name": p_data["fallback_name"],
                    "acronym": p_data["fallback_acronym"],
                    "logo_url": None,
                    "description": "Independent candidate",
                    "founded_date": None,
                    "created_at": datetime.now(timezone.utc)
                }

            formatted_party_results.append({
                "party": party_info,
                "total_votes": p_data["total_votes"],
                "percentage": (p_data["total_votes"] / total_votes * 100) if total_votes > 0 else 0,
                "candidates": p_data["candidates"]
            })

        return StandardResponse(
            status=True,
            data={
                "election": election_serialized,
                "total_votes": total_votes,
                "party_results": formatted_party_results
            },
            message="Election results retrieved successfully"
        )

    except Exception as e:
        print(f" Error in get_election_results: {str(e)}")
        return StandardResponse(
            status=False,
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

# @router.post(
#     "/elections/{election_id}/positions/{position_id}/vote-secure",
#     response_model=StandardResponse[SecureVoteResult]
# )
# async def cast_secure_vote(
#     request: Request,
#     election_id: int,
#     position_id: int,
#     candidate_id: int = Form(...),
#     current_user: User = Depends(get_current_active_user),
#     db: Session = Depends(get_db)
# ):
#     """
#     Cast a secure encrypted vote and automatically send receipt via email
#     """
#     try:
#         ip_address = request.client.host if request.client else None

#         # Cast the vote
#         result = SecureVotingService.cast_encrypted_vote(
#             db=db,
#             user=current_user,
#             election_id=election_id,
#             position_id=position_id,
#             candidate_id=candidate_id,
#             ip_address=ip_address
#         )

#         # 🆕 Send email with vote receipt
#         try:
#             email_sent = email_service.send_vote_receipt_email(
#                 user_email=current_user.email,
#                 user_name=current_user.full_name,
#                 vote_receipt=result["vote_receipt"],
#                 election_name=result["election"],
#                 position_name=result["position"],
#                 candidate_name=result["candidate"],
#                 timestamp=result["timestamp"]
#             )
            
#             if email_sent:
#                 result["email_sent"] = True
#                 result["message"] = "Vote cast successfully! Receipt sent to your email."
#             else:
#                 result["email_sent"] = False
#                 result["message"] = "Vote cast successfully! (Email delivery failed, but your receipt is displayed below)"
                
#         except Exception as email_error:
#             print(f"⚠️ Email sending failed: {str(email_error)}")
#             result["email_sent"] = False
#             result["message"] = "Vote cast successfully! (Email delivery failed, but your receipt is displayed below)"

#         return StandardResponse(
#             status=True,
#             data=SecureVoteResult.model_validate(result),
#             message=result["message"]
#         )

#     except HTTPException as e:
#         return StandardResponse(
#             status=False,
#             error=e.detail.get("error") if isinstance(e.detail, dict) else str(e.detail),
#             message="Failed to cast vote"
#         )

#     except Exception as e:
#         return StandardResponse(
#             status=False,
#             error=str(e),
#             message="Failed to cast vote"
#         )

@router.post("/elections/{election_id}/positions/{position_id}/vote-secure", response_model=StandardResponse[SecureVoteResult])
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
        # 1. Fetch the election record
        election = db.query(Election).filter(Election.id == election_id).first()
        
        if not election:
            raise HTTPException(status_code=404, detail="Election not found")

        # 2. Validate Election Status using your computed property
        # Ensure it is 'ONGOING' and marked as 'is_active'
        if election.status != ElectionStatus.ONGOING:
            status_msg = {
                ElectionStatus.UPCOMING: "Voting has not started yet.",
                ElectionStatus.PAST: "This election has already ended.",
            }.get(election.status, "Voting is currently disabled.")
            
            raise HTTPException(
                status_code=400, 
                detail={"error": "Election not active", "message": status_msg}
            )

        ip_address = request.client.host if request.client else None

        # 3. Cast the vote (Proceed only if checks pass)
        result = SecureVotingService.cast_encrypted_vote(
            db=db,
            user=current_user,
            election_id=election_id,
            position_id=position_id,
            candidate_id=candidate_id,
            ip_address=ip_address
        )

        # ---- Email Logic ----
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
            
            result["email_sent"] = email_sent
            result["message"] = "Vote cast successfully! Receipt sent to your email." if email_sent else "Vote cast successfully! (Email delivery failed)"
                
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
        # Handle the custom election status error here
        return StandardResponse(
            status=False,
            error=e.detail.get("error") if isinstance(e.detail, dict) else str(e.detail),
            message=e.detail.get("message") if isinstance(e.detail, dict) else "Failed to cast vote"
        )

    except Exception as e:
        return StandardResponse(
            status=False,
            error=str(e),
            message="An unexpected error occurred while casting your vote"
        )
    
@router.post("/vote/details-by-receipt", response_model=StandardResponse[dict])
async def get_vote_details_by_receipt(
    vote_receipt: str = Form(..., description="Vote receipt code"),
    db: Session = Depends(get_db)
):
    try:
        def safe_val(attr):
            return attr.value if hasattr(attr, 'value') else attr

        # Corrected nested path
        ev = db.query(EncryptedVote).options(
            joinedload(EncryptedVote.election),
            joinedload(EncryptedVote.position),
            joinedload(EncryptedVote.candidate).joinedload(Candidate.user),
            joinedload(EncryptedVote.candidate).joinedload(Candidate.party)
        ).filter(EncryptedVote.vote_receipt == vote_receipt).first()

        if not ev:
            return StandardResponse(
                status=False,
                error="NOT_FOUND",
                message="Invalid receipt code. No record found."
            )

        # Build response safely
        vote_details = {
            "vote_receipt": ev.vote_receipt,
            "verification": {
                "is_verified": ev.verified,
                "is_tallied": ev.tallied,
                "status_label": "Verified and Counted" if ev.tallied else "Pending Final Tally",
                "timestamp": ev.cast_at.isoformat() if ev.cast_at else None
            },
            "election": {
                "id": ev.election.id,
                "title": ev.election.title,
                "type": safe_val(ev.election.election_type),
                "current_status": safe_val(ev.election.status) 
            },
            "ballot_item": {
                "position": ev.position.title if ev.position else "Unknown",
                "candidate": ev.candidate.user.full_name if (ev.candidate and ev.candidate.user) else "Unknown",
                "party": ev.candidate.party.acronym if (ev.candidate and ev.candidate.party) else "IND"
            }
        }

        return StandardResponse(
            status=True,
            data=vote_details,
            message="Vote details retrieved successfully"
        )

    except Exception as e:
        print(f" Mapper Error: {str(e)}")
        return StandardResponse(
            status=False,
            error="SERVER_ERROR",
            message="An internal database mapping error occurred."
        )
    
@router.get("/my-votes", response_model=StandardResponse[dict])
async def get_my_votes(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all votes cast by the current user across all elections.
    Groups votes by election for a clear participation history.
    """
    try:
        # Helper for Enum safety
        def safe_val(attr):
            return attr.value if hasattr(attr, 'value') else attr

        # 1. Fetch all elections to check participation
        elections = db.query(Election).all()
        votes_by_election = []
        total_votes_count = 0

        for election in elections:
            election_votes = []
            
            # Fetch positions for this specific election
            positions = db.query(Position).filter(Position.election_id == election.id).all()
            
            for position in positions:
                # Reconstruct the anonymous ID for this specific position
                # This ensures the link remains private in the DB but accessible to the owner
                anon_id = SecureVotingService._generate_anonymous_id(
                    current_user.id, election.id, position.id
                )
                
                # Check for the vote
                vote = db.query(EncryptedVote).filter(
                    EncryptedVote.anonymous_voter_id == anon_id,
                    EncryptedVote.election_id == election.id,
                    EncryptedVote.position_id == position.id
                ).first()

                if vote:
                    # Get candidate info with joined user/party
                    candidate = db.query(Candidate).options(
                        joinedload(Candidate.user),
                        joinedload(Candidate.party)
                    ).filter(Candidate.id == vote.candidate_id).first()

                    election_votes.append({
                        "position_title": position.title,
                        "candidate_name": candidate.user.full_name if candidate and candidate.user else "Unknown",
                        "party_acronym": candidate.party.acronym if candidate and candidate.party else "IND",
                        "vote_receipt": vote.vote_receipt,
                        "cast_at": vote.cast_at,
                        "status": "Counted" if vote.tallied else "Verified"
                    })
                    total_votes_count += 1

            # Only add to results if the user actually voted in this election
            if election_votes:
                votes_by_election.append({
                    "election_details": {
                        "id": election.id,
                        "title": election.title,
                        "status": safe_val(election.status), # Accesses your @property
                        "type": safe_val(election.election_type)
                    },
                    "my_ballot": election_votes
                })

        return StandardResponse(
            status=True,
            data={
                "summary": {
                    "total_votes_cast": total_votes_count,
                    "elections_attended": len(votes_by_election)
                },
                "history": votes_by_election
            },
            message="Voting history retrieved successfully"
        )

    except Exception as e:
        print(f" Error in get_my_votes: {str(e)}")
        return StandardResponse(
            status=False,
            error=str(e),
            message="Error retrieving your voting history"
        )
  
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

@router.get("/upcoming", response_model=StandardResponse[List[ElectionResponse]])
def get_upcoming_elections(db: Session = Depends(get_db)):
    """Retrieve elections that haven't started yet"""
    try:
        now = datetime.now(timezone.utc)

        elections = (
            db.query(Election)
            .filter(Election.start_date > now)
            .order_by(Election.start_date.asc())
            .all()
        )

        # Using a list comprehension with model_validate 
        # (Ensure your ElectionResponse has from_attributes=True)
        elections_response = [
            ElectionResponse.model_validate(election)
            for election in elections
        ]

        return StandardResponse(
            status=True,
            message=f"Retrieved {len(elections_response)} upcoming elections",
            data=elections_response
        )
    except Exception as e:
        return StandardResponse(status=False, error=str(e), message="Failed to fetch upcoming elections")
    
@router.get("/past", response_model=StandardResponse[List[ElectionResponse]])
def get_past_elections(db: Session = Depends(get_db)):
    """Retrieve completed elections"""
    try:
        now = datetime.now(timezone.utc)

        elections = (
            db.query(Election)
            .filter(Election.end_date < now)
            .order_by(Election.end_date.desc()) # Newest past elections first
            .all()
        )

        elections_response = [
            ElectionResponse.model_validate(election)
            for election in elections
        ]

        return StandardResponse(
            status=True,
            message=f"Retrieved {len(elections_response)} past elections",
            data=elections_response
        )
    except Exception as e:
        return StandardResponse(status=False, error=str(e), message="Failed to fetch past elections")
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