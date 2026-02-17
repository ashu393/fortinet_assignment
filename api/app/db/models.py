from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "techcorp"
    name: Mapped[str] = mapped_column(String, nullable=False)

    users = relationship("User", back_populates="organization")
    documents = relationship("Document", back_populates="organization")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "alice"
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # admin/analyst/viewer

    organization_id: Mapped[str] = mapped_column(String, ForeignKey("organizations.id"), nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="users")


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "TC-1042"
    title: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)

    organization_id: Mapped[str] = mapped_column(String, ForeignKey("organizations.id"), nullable=False)
    uploaded_by_user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="documents")


class DocumentShare(Base):
    """
    Explicit sharing of a document to another user (within same org).
    Analysts can share with other analysts; viewers can only read shared docs.
    """
    __tablename__ = "document_shares"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # uuid str
    document_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id"), nullable=False)
    shared_with_user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    shared_by_user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    can_read: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("document_id", "shared_with_user_id", name="uq_doc_share"),
    )


class GuardrailSettings(Base):
    __tablename__ = "guardrail_settings"
    organization_id: Mapped[str] = mapped_column(String, ForeignKey("organizations.id"), primary_key=True)
    hallucination_confidence_threshold: Mapped[float] = mapped_column(nullable=False, default=0.70)
    pii_redaction_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    require_citations: Mapped[bool] = mapped_column(Boolean, default=True)
    blocked_keywords_csv: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)