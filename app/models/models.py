from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
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

class User(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    nin = Column(String(20), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    state_of_residence = Column(
        Enum(
            State,
            values_callable=lambda obj: [e.value for e in obj],  # use .value
            native_enum=False
        ),
        nullable=False
    )

    profile_image_url = Column(String(500), nullable=True)
    hashed_password = Column(String(255), nullable=False)

    role = Column(
        Enum(
            UserRole,
            values_callable=lambda obj: [e.value for e in obj],  # use .value
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

    positions = relationship("Position", back_populates="election")
    votes = relationship("Vote", back_populates="election")


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False)

    election = relationship("Election", back_populates="positions")
    candidates = relationship("Candidate", back_populates="position")


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    bio = Column(Text)
    profile_image_url = Column(String(500), nullable=True)
    party_id = Column(Integer, ForeignKey("political_parties.id"), nullable=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=False)

    position = relationship("Position", back_populates="candidates")
    votes = relationship("Vote", back_populates="candidate")
    party = relationship("PoliticalParty")


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

    user = relationship("User")
    candidate = relationship("Candidate", back_populates="votes")
    election = relationship("Election", back_populates="votes")
