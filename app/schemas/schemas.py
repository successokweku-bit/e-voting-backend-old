from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List, Generic, TypeVar
from datetime import datetime, date
from enum import Enum

from app.models.models import UserRole, State, ElectionType

T = TypeVar("T")

# -------------------------
# STANDARD RESPONSE
# -------------------------
class StandardResponse(BaseModel, Generic[T]):
    status: bool
    data: Optional[T] = None
    error: Optional[str] = None
    message: Optional[str] = None

    model_config = {
        "from_attributes": True
    }

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

    model_config = {
        "from_attributes": True
    }

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
    @validator("state_of_residence", pre=True)
    def normalize_state(cls, v):
        if isinstance(v, State):
            return v
        v_str = str(v).strip().lower()
        for state in State:
            if v_str == state.value.lower():
                return state
        raise ValueError(f"Invalid state '{v}'. Allowed values: {[s.value for s in State]}")

    # Normalize role
    @validator("role", pre=True)
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

    @validator("password")
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v

    @validator("nin")
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

    model_config = {
        "from_attributes": True
    }

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

    @validator("new_password")
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v

# -------------------------
# ELECTION SCHEMAS
# -------------------------
class ElectionBase(BaseModel):
    title: str
    description: Optional[str] = None
    election_type: ElectionType
    state: Optional[State] = None
    is_active: bool = False
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class ElectionCreate(ElectionBase):
    pass

class ElectionResponse(ElectionBase):
    id: int
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

class PositionBase(BaseModel):
    title: str
    description: Optional[str] = None

class PositionCreate(PositionBase):
    election_id: int

class PositionResponse(PositionBase):
    id: int
    election_id: int

    model_config = {
        "from_attributes": True
    }

class CandidateBase(BaseModel):
    name: str
    bio: Optional[str] = None
    profile_image_url: Optional[str] = None

class CandidateCreate(CandidateBase):
    position_id: int
    party_id: Optional[int] = None

class CandidateResponse(CandidateBase):
    id: int
    position_id: int
    party: Optional[PoliticalPartyResponse] = None

    model_config = {
        "from_attributes": True
    }

class VoteRequest(BaseModel):
    candidate_id: int

class VoteResponse(BaseModel):
    vote_id: int
    message: str

    model_config = {
        "from_attributes": True
    }

# -------------------------
# EXTENDED SCHEMAS
# -------------------------
class CandidateWithVotes(CandidateResponse):
    votes_count: int = 0

class PositionWithCandidates(PositionResponse):
    candidates: List[CandidateWithVotes] = []

class ElectionWithPositions(ElectionResponse):
    positions: List[PositionWithCandidates] = []
    total_votes: int = 0

class VoterProfile(BaseModel):
    user: UserResponse
    total_votes_cast: int
    elections_participated: List[str]

    model_config = {
        "from_attributes": True
    }

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

    model_config = {
        "from_attributes": True
    }
