from pydantic import BaseModel, EmailStr, field_validator, ConfigDict, Field
from typing import Optional, List, Generic, TypeVar, Any
from datetime import datetime, date
from enum import Enum

from app.models.models import UserRole, State, ElectionType

T = TypeVar("T")

# -------------------------
# STANDARD RESPONSE
# -------------------------
# class StandardResponse(BaseModel, Generic[T]):
#     status: bool
#     data: Optional[T] = None
#     error: Optional[Any] = None
#     message: Optional[str] = None

#     model_config = ConfigDict(from_attributes=True)


class StandardResponse(BaseModel, Generic[T]):
    status: bool
    data: Optional[T] = None
    error: Optional[Any] = None
    message: Optional[str] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        from_attributes=True
    )

# -------------------------
# POLITICAL PARTY SCHEMAS
# -------------------------
class PoliticalPartyBase(BaseModel):
    name: str
    acronym: str
    logo_url: Optional[str] = None
    description: Optional[str] = None
    founded_date: Optional[datetime] = None

class PoliticalPartyCreate(PoliticalPartyBase):
    pass

class PoliticalPartyResponse(PoliticalPartyBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# -------------------------
# USER SCHEMAS
# -------------------------
class UserBase(BaseModel):
    nin: str
    email: EmailStr
    full_name: str
    state_of_residence: State
    profile_image_url: Optional[str] = None
    date_of_birth: Optional[date] = None
    role: UserRole = UserRole.USER

    # Normalize state
    @field_validator("state_of_residence", mode="before")
    @classmethod
    def normalize_state(cls, v):
        if isinstance(v, State):
            return v
        v_str = str(v).strip().lower()
        for state in State:
            if v_str == state.value.lower():
                return state
        raise ValueError(f"Invalid state '{v}'. Allowed values: {[s.value for s in State]}")

    # Normalize role
    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v):
        if isinstance(v, UserRole):
            return v
        v_str = str(v).strip().lower()
        for role in UserRole:
            if v_str == role.value.lower():
                return role
        raise ValueError(f"Invalid role '{v}'. Allowed values: {[r.value for r in UserRole]}")

class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v

    @field_validator("nin")
    @classmethod
    def nin_length(cls, v):
        if len(v) != 11:
            raise ValueError("NIN must be 11 digits long")
        if not v.isdigit():
            raise ValueError("NIN must contain only digits")
        return v

class UserResponse(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    registration_date: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# -------------------------
# AUTH SCHEMAS
# -------------------------
class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class TokenData(BaseModel):
    username: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

# -------------------------
# OTP SCHEMAS
# -------------------------
class OTPVerificationRequest(BaseModel):
    email: EmailStr
    otp_code: str

class OTPResponse(BaseModel):
    message: str
    email: EmailStr

# -------------------------
# PASSWORD RESET
# -------------------------
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v

# -------------------------
# ELECTION SCHEMAS
# -------------------------
class ElectionBase(BaseModel):
    title: str
    description: str | None
    election_type: ElectionType
    state: State | None
    is_active: bool
    start_date: datetime | None
    end_date: datetime | None

class ElectionCreate(ElectionBase):
    pass

class ElectionStatus(str, Enum):
    UPCOMING = "upcoming"
    ONGOING = "ongoing"
    PAST = "past"

class ElectionResponse(ElectionBase):
    id: int
    created_at: datetime
    status: ElectionStatus
    model_config = ConfigDict(from_attributes=True)


class PositionBase(BaseModel):
    title: str
    description: Optional[str] = None

class PositionCreate(PositionBase):
    election_id: int

class PositionResponse(PositionBase):
    id: int
    election_id: int

    model_config = ConfigDict(from_attributes=True)

class CandidateBase(BaseModel):
    name: str
    bio: Optional[str] = None
    profile_image_url: Optional[str] = None

class ManifestoItem(BaseModel):
    title: str
    description: str

class CandidateCreate(BaseModel):
    user_id: int
    position_id: int
    election_id: int
    party_id: Optional[int] = None
    bio: Optional[str] = None
    manifestos: Optional[List[ManifestoItem]] = Field(default_factory=list)


# class CandidateResponse(CandidateBase):
#     id: int
#     user_id: int
#     position_id: int
#     election_id: int
#     party: Optional[PoliticalPartyResponse] = None
#     manifestos: Optional[List[ManifestoItem]] = []

#     model_config = ConfigDict(from_attributes=True)

class ElectionInfo(BaseModel):
    id: int
    title: str
    description: Optional[str]
    election_type: Optional[str]
    state: Optional[str]
    start_date: Optional[datetime]
    end_date: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

class CandidateResponse(BaseModel):
    id: int
    user_id: int
    name: str  # From User table
    position_id: int
    party_id: Optional[int]
    bio: Optional[str]
    manifestos: Optional[List[dict]]
    election: Optional[ElectionInfo]

    model_config = ConfigDict(from_attributes=True)

class PartyResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    logo_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class CandidateElectionResponse(BaseModel):
    id: int
    user_id: int
    name: str
    position_id: int
    bio: Optional[str]
    manifestos: Optional[List[dict]]
    party: Optional[PartyResponse]
    election: Optional[ElectionInfo]

    model_config = ConfigDict(from_attributes=True)

class CandidateWithVotes(CandidateResponse):
    votes_count: int = 0

class VoteRequest(BaseModel):
    candidate_id: int

class VoteResponse(BaseModel):
    vote_id: int
    message: str

    model_config = ConfigDict(from_attributes=True)

class PositionWithCandidates(PositionResponse):
    candidates: List[CandidateWithVotes] = Field(default_factory=list)

class ElectionWithPositions(ElectionResponse):
    positions: List[PositionWithCandidates] = Field(default_factory=list)
    total_votes: int = 0

class VoterProfile(BaseModel):
    user: UserResponse
    total_votes_cast: int
    elections_participated: List[str]

    model_config = ConfigDict(from_attributes=True)

class PartyResults(BaseModel):
    party: PoliticalPartyResponse
    total_votes: int
    percentage: float
    candidates: List[CandidateWithVotes]

class ElectionResultsDetailed(BaseModel):
    election: ElectionResponse
    party_results: List[PartyResults]
    total_votes: int
    voter_turnout: float

    model_config = ConfigDict(from_attributes=True)

# class CandidateUserResponse(BaseModel):
#     id: int
#     user_id: int
#     full_name: str
#     party_name: str | None
#     position_id: int
#     election_id: int
#     bio: str | None
#     manifestos: list | None

#     class Config:
#         from_attributes = True


# Update the existing SecureVoteResult schema to include email_sent field
class SecureVoteResult(BaseModel):
    """Response model for secure vote casting"""
    message: str
    vote_receipt: str
    election: str
    position: str
    candidate: str
    timestamp: str
    instructions: str
    email_sent: Optional[bool] = False 
    
    model_config = ConfigDict(from_attributes=True)


#  New schema for vote details by receipt
class VotePartyInfo(BaseModel):
    """Party information in vote details"""
    name: str
    acronym: str
    logo_url: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class VoteCandidateInfo(BaseModel):
    """Candidate information in vote details"""
    id: int
    name: str
    bio: Optional[str] = None
    party: Optional[VotePartyInfo] = None
    
    model_config = ConfigDict(from_attributes=True)


class VoteElectionInfo(BaseModel):
    """Election information in vote details"""
    id: int
    title: str
    description: Optional[str] = None
    election_type: Optional[str] = None
    state: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class VotePositionInfo(BaseModel):
    """Position information in vote details"""
    id: int
    title: str
    description: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class VoteDetailsByReceipt(BaseModel):
    """Complete vote details retrieved by receipt"""
    vote_receipt: str
    election: Optional[VoteElectionInfo] = None
    position: Optional[VotePositionInfo] = None
    candidate: Optional[VoteCandidateInfo] = None
    cast_at: Optional[str] = None
    verified: bool = False
    tallied: bool = False
    vote_hash: Optional[str] = None
    status: str
    
    model_config = ConfigDict(from_attributes=True)


# New schemas for "My Votes" endpoint
class MyVoteParty(BaseModel):
    """Party information in my votes"""
    id: int
    name: str
    acronym: str
    logo_url: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class MyVoteCandidate(BaseModel):
    """Candidate information in my votes"""
    id: int
    name: str
    bio: Optional[str] = None
    manifestos: Optional[List[str]] = []
    party: Optional[MyVoteParty] = None
    
    model_config = ConfigDict(from_attributes=True)


class MyVotePosition(BaseModel):
    """Position information in my votes"""
    id: int
    title: str
    description: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class MyVoteElection(BaseModel):
    """Election information in my votes"""
    id: int
    title: str
    description: Optional[str] = None
    election_type: Optional[str] = None
    state: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_active: bool = False
    
    model_config = ConfigDict(from_attributes=True)


class MyVoteInfo(BaseModel):
    """Individual vote information"""
    vote_receipt: str
    position: MyVotePosition
    candidate: Optional[MyVoteCandidate] = None
    cast_at: Optional[str] = None
    verified: bool = False
    status: str
    
    model_config = ConfigDict(from_attributes=True)


class MyVotesByElection(BaseModel):
    """Votes grouped by election"""
    election: MyVoteElection
    votes: List[MyVoteInfo]
    
    model_config = ConfigDict(from_attributes=True)


class MyVotesComplete(BaseModel):
    """Complete vote information (flat)"""
    vote_id: int
    vote_receipt: str
    election: MyVoteElection
    position: MyVotePosition
    candidate: Optional[MyVoteCandidate] = None
    cast_at: Optional[str] = None
    verified: bool = False
    tallied: bool = False
    status: str
    
    model_config = ConfigDict(from_attributes=True)


class MyVotesResponse(BaseModel):
    """Response for my votes endpoint"""
    total_votes: int
    total_elections_participated: int
    votes_by_election: List[MyVotesByElection]
    all_votes: List[MyVotesComplete]
    
    model_config = ConfigDict(from_attributes=True)


# Example usage in route response model:
# @router.get("/my-votes", response_model=StandardResponse[MyVotesResponse])
# async def get_my_votes(...):
#     ...