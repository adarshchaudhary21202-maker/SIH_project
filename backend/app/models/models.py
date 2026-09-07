import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)  # OFFICER, SUPERVISOR, ADMIN
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    users: Mapped[List["User"]] = relationship("User", back_populates="role_rel")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    badge_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(50))  # Denormalized string copy or linked via relationship
    role_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("roles.id"), nullable=True)
    account_status: Mapped[str] = mapped_column(String(50), default="ACTIVE")  # ACTIVE, SUSPENDED, INACTIVE
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    role_rel: Mapped[Optional[Role]] = relationship("Role", back_populates="users")
    cases: Mapped[List["Case"]] = relationship("Case", back_populates="officer")
    test_sessions: Mapped[List["TestSession"]] = relationship("TestSession", back_populates="officer")


class OTPVerification(Base):
    __tablename__ = "otp_verifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    badge_id: Mapped[str] = mapped_column(String(50), index=True)
    otp_hash: Mapped[str] = mapped_column(String(255))  # Argon2id hash of the OTP code
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    resend_available_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    badge_id: Mapped[str] = mapped_column(String(50), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DeviceSession(Base):
    __tablename__ = "device_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    badge_id: Mapped[str] = mapped_column(String(50), index=True)
    device_id: Mapped[str] = mapped_column(String(100), index=True)
    device_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    case_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_officer_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.badge_id"))
    status: Mapped[str] = mapped_column(String(50), default="OPEN")  # OPEN, CLOSED, UNDER_REVIEW
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    officer: Mapped[User] = relationship("User", back_populates="cases")
    test_sessions: Mapped[List["TestSession"]] = relationship("TestSession", back_populates="case")
    evidence_records: Mapped[List["EvidenceRecord"]] = relationship("EvidenceRecord", back_populates="case")


class TestKit(Base):
    __tablename__ = "test_kits"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kit_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    batch_number: Mapped[str] = mapped_column(String(100), index=True)
    manufacturing_date: Mapped[datetime] = mapped_column(DateTime)
    expiry_date: Mapped[datetime] = mapped_column(DateTime)
    reagent_information: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="VALID")  # VALID, EXPIRED, INVALID
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TestSession(Base):
    __tablename__ = "test_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    officer_badge_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.badge_id"), index=True)
    device_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("device_sessions.id"))
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"))
    test_kit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_kits.id"))
    gps_latitude: Mapped[str] = mapped_column(String(50))
    gps_longitude: Mapped[str] = mapped_column(String(50))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="STARTED")  # STARTED, COMPLETED, ABANDONED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    officer: Mapped[User] = relationship("User", back_populates="test_sessions")
    case: Mapped[Case] = relationship("Case", back_populates="test_sessions")


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"))
    test_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_sessions.id"))
    officer_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.badge_id"))
    kit_id: Mapped[str] = mapped_column(String(100), ForeignKey("test_kits.kit_id"))
    batch: Mapped[str] = mapped_column(String(100))
    expiry: Mapped[datetime] = mapped_column(DateTime)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    gps_latitude: Mapped[str] = mapped_column(String(50))
    gps_longitude: Mapped[str] = mapped_column(String(50))
    device_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("device_sessions.id"))
    original_image_reference: Mapped[str] = mapped_column(String(255))
    ai_result: Mapped[str] = mapped_column(String(100))
    ai_confidence: Mapped[float] = mapped_column(Float)
    image_quality: Mapped[float] = mapped_column(Float)
    calibration_score: Mapped[float] = mapped_column(Float)
    sha256_hash: Mapped[str] = mapped_column(String(64))  # Secure hash of deterministic evidence payload
    digital_signature: Mapped[str] = mapped_column(String(128))  # Ed25519 signature
    qr_reference: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING_REVIEW")  # PENDING_REVIEW, APPROVED, REJECTED, CORRECTION_PENDING
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    case: Mapped[Case] = relationship("Case", back_populates="evidence_records")
    versions: Mapped[List["EvidenceVersion"]] = relationship("EvidenceVersion", back_populates="evidence_record")
    correction_requests: Mapped[List["CorrectionRequest"]] = relationship("CorrectionRequest", back_populates="evidence")


class EvidenceVersion(Base):
    __tablename__ = "evidence_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evidence_record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence_records.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    changed_by_badge_id: Mapped[str] = mapped_column(String(50))
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    changes_json: Mapped[str] = mapped_column(Text)  # JSON representation of changed fields
    reason: Mapped[str] = mapped_column(Text)
    approval_status: Mapped[str] = mapped_column(String(50), default="PENDING")  # PENDING, APPROVED, REJECTED
    approver_badge_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    evidence_record: Mapped[EvidenceRecord] = relationship("EvidenceRecord", back_populates="versions")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor_badge_id: Mapped[str] = mapped_column(String(50), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resource_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    before_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON or descriptive string
    after_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # JSON or descriptive string
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    device_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChainOfCustodyEvent(Base):
    __tablename__ = "chain_of_custody_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence_records.id"), index=True)
    from_user_badge_id: Mapped[str] = mapped_column(String(50))
    to_user_badge_id: Mapped[str] = mapped_column(String(50))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    location: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text)
    authorization_reference: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CorrectionRequest(Base):
    __tablename__ = "correction_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evidence_records.id"), index=True)
    requested_by_badge_id: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")  # PENDING, APPROVED, REJECTED
    reviewed_by_badge_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proposed_changes_json: Mapped[str] = mapped_column(Text)  # JSON representation of proposed correction
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    evidence: Mapped[EvidenceRecord] = relationship("EvidenceRecord", back_populates="correction_requests")


