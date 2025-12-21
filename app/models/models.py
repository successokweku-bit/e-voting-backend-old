from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum, UniqueConstraint, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime,timezone
import enum

Base = declarative_base()

# -------------------------
# ENUM DEFINITIONS
# -------------------------

class UserRole(enum.Enum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

class State(enum.Enum):
    ABIA = "Abia"
    ADAMAWA = "Adamawa"
    AKWA_IBOM = "Akwa Ibom"
    ANAMBRA = "Anambra"
    BAUCHI = "Bauchi"
    BAYELSA = "Bayelsa"
    BENUE = "Benue"
    BORNO = "Borno"
    CROSS_RIVER = "Cross River"
    DELTA = "Delta"
    EBONYI = "Ebonyi"
    EDO = "Edo"
    EKITI = "Ekiti"
    ENUGU = "Enugu"
    FCT = "Federal Capital Territory"
    GOMBE = "Gombe"
    IMO = "Imo"
    JIGAWA = "Jigawa"
    KADUNA = "Kaduna"
    KANO = "Kano"
    KATSINA = "Katsina"
    KEBBI = "Kebbi"
    KOGI = "Kogi"
    KWARA = "Kwara"
    LAGOS = "Lagos"
    NASARAWA = "Nasarawa"
    NIGER = "Niger"
    OGUN = "Ogun"
    ONDO = "Ondo"
    OSUN = "Osun"
    OYO = "Oyo"
    PLATEAU = "Plateau"
    RIVERS = "Rivers"
    SOKOTO = "Sokoto"
    TARABA = "Taraba"
    YOBE = "Yobe"
    ZAMFARA = "Zamfara"

class ElectionType(enum.Enum):
    FEDERAL = "federal"
    STATE = "state"
    LOCAL = "local"

class ElectionStatus(str, Enum):
    UPCOMING = "upcoming"
    ONGOING = "ongoing"
    PAST = "past"

# -------------------------
# MODELS
# -------------------------

class PoliticalParty(Base):
    __tablename__ = "political_parties"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    acronym = Column(String(50), unique=True, nullable=False)
    logo_url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    founded_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    candidates = relationship("Candidate", back_populates="party")


class User(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    nin = Column(String(20), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    state_of_residence = Column(
        Enum(
            State,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False
        ),
        nullable=False
    )
    profile_image_url = Column(String(500), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(
        Enum(
            UserRole,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False
        ),
        default=UserRole.USER.value,
        nullable=False
    )
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    date_of_birth = Column(DateTime(timezone=True), nullable=True)
    registration_date = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    votes = relationship("Vote", back_populates="user")
    candidates = relationship("Candidate", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")
    tallies = relationship("ElectionTally", back_populates="tally_admin")


class OTP(Base):
    __tablename__ = "otps"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False)
    otp_code = Column(String(6), nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)


class Election(Base):
    __tablename__ = "elections"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    election_type = Column(
        Enum(
            ElectionType,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False
        ),
        nullable=False
    )
    state = Column(
        Enum(
            State,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False
        ),
        nullable=True
    )
    is_active = Column(Boolean, default=False)
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    positions = relationship("Position", back_populates="election")
    votes = relationship("Vote", back_populates="election")
    encrypted_votes = relationship("EncryptedVote", back_populates="election")
    candidates = relationship("Candidate", back_populates="election")
    tallies = relationship("ElectionTally", back_populates="election")

    @property
    def status(self) -> ElectionStatus:
        now = datetime.now(timezone.utc)

        if self.start_date and now < self.start_date:
            return ElectionStatus.UPCOMING

        if self.end_date and self.start_date <= now <= self.end_date:
            return ElectionStatus.ONGOING

        return ElectionStatus.PAST

class Position(Base):
    __tablename__ = "positions"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False)

    # Relationships
    election = relationship("Election", back_populates="positions")
    candidates = relationship("Candidate", back_populates="position")
    encrypted_votes = relationship("EncryptedVote", back_populates="position")


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (
        UniqueConstraint('user_id', 'position_id', 'election_id', name='unique_candidate_per_position_election'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    election_id = Column(Integer, ForeignKey("elections.id", ondelete="CASCADE"), nullable=False)
    position_id = Column(Integer, ForeignKey("positions.id", ondelete="CASCADE"), nullable=False)
    party_id = Column(Integer, ForeignKey("political_parties.id", ondelete="SET NULL"), nullable=True)
    bio = Column(Text, nullable=True)
    manifestos = Column(JSON, nullable=True, default=list)

    # Relationships
    user = relationship("User", back_populates="candidates")
    election = relationship("Election", back_populates="candidates")
    position = relationship("Position", back_populates="candidates")
    party = relationship("PoliticalParty", back_populates="candidates")
    votes = relationship("Vote", back_populates="candidate")
    encrypted_votes = relationship("EncryptedVote", back_populates="candidate")


class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (
        UniqueConstraint('user_id', 'election_id', name='unique_user_election'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False)
    encrypted_vote = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="votes")
    candidate = relationship("Candidate", back_populates="votes")
    election = relationship("Election", back_populates="votes")


# ==================== SECURE VOTING MODELS ====================

class EncryptedVote(Base):
    """
    Stores encrypted votes with anonymization and integrity verification
    """
    __tablename__ = "encrypted_votes"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Anonymized voter ID (cannot be traced back to user)
    anonymous_voter_id = Column(String(64), nullable=False, index=True)
    
    # Election reference
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False)
    
    # Position reference (for your multi-position elections)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=False)
    
    # Candidate reference (for tallying)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    
    # Encrypted vote data (contains user_id, candidate_id internally)
    encrypted_vote_data = Column(Text, nullable=False)
    
    # Integrity verification
    vote_hash = Column(String(64), nullable=False, unique=True, index=True)
    
    # Receipt for voter verification
    vote_receipt = Column(String(20), nullable=False, unique=True, index=True)
    receipt_hash = Column(String(64), nullable=False, unique=True)
    
    # Zero-knowledge commitment
    commitment_hash = Column(String(64), nullable=False)
    
    # Metadata
    cast_at = Column(DateTime(timezone=True), default=func.now, nullable=False)
    
    # Verification status (set during tallying)
    verified = Column(Boolean, default=False)
    tallied = Column(Boolean, default=False)
    
    # Relationships
    election = relationship("Election", back_populates="encrypted_votes")
    position = relationship("Position", back_populates="encrypted_votes")
    candidate = relationship("Candidate", back_populates="encrypted_votes")
    commitment = relationship("VoteCommitment", back_populates="encrypted_vote", uselist=False)
    verifications = relationship("VoteVerification", back_populates="encrypted_vote")
    
    def __repr__(self):
        return f"<EncryptedVote(id={self.id}, election={self.election_id}, receipt={self.vote_receipt})>"


class VoteCommitment(Base):
    """
    Stores commitment factors separately for zero-knowledge proofs
    Only accessible to super admin during tallying
    """
    __tablename__ = "vote_commitments"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Links to encrypted vote (but stored separately)
    vote_hash = Column(String(64), ForeignKey("encrypted_votes.vote_hash"), nullable=False, unique=True)
    
    # Commitment factor (random string used in commitment)
    commitment_factor = Column(String(64), nullable=False)
    
    # Timestamps
    # created_at = Column(DateTime(timezone=True), default=func.now, nullable=False)
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(), # <--- Use server_default and CALL func.now()
        nullable=False
    )
    
    # Relationships
    encrypted_vote = relationship("EncryptedVote", back_populates="commitment")
    
    def __repr__(self):
        return f"<VoteCommitment(vote_hash={self.vote_hash[:16]}...)>"


class AuditLog(Base):
    """
    Immutable audit trail with blockchain-style hash chaining
    """
    __tablename__ = "audit_logs"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Action performed
    action = Column(String(100), nullable=False, index=True)
    
    # User who performed action
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Action details (JSON string)
    details = Column(Text, nullable=True)
    
    # Hash chaining (blockchain-style)
    previous_hash = Column(String(64), nullable=True)
    current_hash = Column(String(64), nullable=False, unique=True, index=True)
    
    # Timestamps
    # created_at = Column(DateTime(timezone=True), default=func.now, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(),nullable=False)

    # IP address and user agent
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, user={self.user_id})>"


class VoteVerification(Base):
    """
    Records when voters verify their vote receipts
    """
    __tablename__ = "vote_verifications"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Receipt being verified
    vote_receipt = Column(String(20), ForeignKey("encrypted_votes.vote_receipt"), nullable=False)
    
    # Verification details
    verified_at = Column(DateTime(timezone=True), default=func.now, nullable=False)
    ip_address = Column(String(45), nullable=True)
    
    # Result
    verification_successful = Column(Boolean, default=True)
    
    # Relationships
    encrypted_vote = relationship("EncryptedVote", back_populates="verifications")
    
    def __repr__(self):
        return f"<VoteVerification(receipt={self.vote_receipt}, verified_at={self.verified_at})>"


class UserSession(Base):
    """
    Track user sessions for security (can revoke all sessions)
    """
    __tablename__ = "user_sessions"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    
    # User reference
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Session token (JWT ID)
    jti = Column(String(36), nullable=False, unique=True, index=True)
    
    # Session details
    created_at = Column(DateTime(timezone=True), default=func.now, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_activity = Column(DateTime(timezone=True), default=func.now, nullable=False)
    
    # Device info
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    def __repr__(self):
        return f"<UserSession(user={self.user_id}, jti={self.jti[:8]}...)>"


class ElectionTally(Base):
    """
    Records when elections are tallied (for audit trail)
    """
    __tablename__ = "election_tallies"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Election reference
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False)
    
    # Who performed the tally
    tallied_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # When
    # tallied_at = Column(DateTime(timezone=True), default=func.now, nullable=False)
    tallied_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Results summary (JSON string)
    results_summary = Column(Text, nullable=True)
    
    # Verification
    total_votes_decrypted = Column(Integer, default=0)
    total_votes_verified = Column(Integer, default=0)
    integrity_check_passed = Column(Boolean, default=True)
    
    # Audit trail hash
    audit_hash = Column(String(64), nullable=False, unique=True)
    
    # Relationships
    election = relationship("Election", back_populates="tallies")
    tally_admin = relationship("User", back_populates="tallies")
    
    def __repr__(self):
        return f"<ElectionTally(election={self.election_id}, by={self.tallied_by}, at={self.tallied_at})>"