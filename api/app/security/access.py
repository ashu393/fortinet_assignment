from fastapi import HTTPException
from app.db.session import SessionLocal
from app.db.models import Document, DocumentShare, User

ROLE_ADMIN = "admin"
ROLE_ANALYST = "analyst"
ROLE_VIEWER = "viewer"

def get_document_or_404(document_id: str) -> Document:
    db = SessionLocal()
    doc = db.get(Document, document_id)
    db.close()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

def can_user_read_document(user: User, document_id: str) -> bool:
    db = SessionLocal()
    doc = db.get(Document, document_id)
    if not doc:
        db.close()
        return False

    # Hard tenant boundary
    if doc.organization_id != user.organization_id:
        db.close()
        return False

    # Admin can read all in org
    if user.role == ROLE_ADMIN:
        db.close()
        return True

    # Analyst can read docs in org (PoC: allow all org docs)
    if user.role == ROLE_ANALYST:
        db.close()
        return True

    # Viewer: only if explicitly shared
    if user.role == ROLE_VIEWER:
        shared = (
            db.query(DocumentShare)
            .filter(
                DocumentShare.document_id == document_id,
                DocumentShare.shared_with_user_id == user.id,
                DocumentShare.can_read == True,
            )
            .first()
        )
        db.close()
        return shared is not None

    db.close()
    return False

def require_document_read_access(user: User, document_id: str):
    if not can_user_read_document(user, document_id):
        raise HTTPException(status_code=403, detail="Forbidden")