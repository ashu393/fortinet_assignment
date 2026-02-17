# api/app/routers/documents.py

from pathlib import Path
import uuid

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel

from app.security.deps import get_current_user
from app.security.access import get_document_or_404, require_document_read_access
from app.db.models import User, Document, DocumentShare
from app.db.session import SessionLocal

router = APIRouter()


class ShareRequest(BaseModel):
    shared_with_user_id: str  # e.g. "charlie"


@router.post("/{document_id}/share")
def share_document(document_id: str, payload: ShareRequest, user: User = Depends(get_current_user)):
    # Only admin/analyst can share
    if user.role not in ("admin", "analyst"):
        raise HTTPException(status_code=403, detail="Forbidden")

    db = SessionLocal()

    # Document must exist
    doc = db.get(Document, document_id)
    if not doc:
        db.close()
        raise HTTPException(status_code=404, detail="Document not found")

    # Hard tenant boundary
    if doc.organization_id != user.organization_id:
        db.close()
        raise HTTPException(status_code=403, detail="Forbidden")

    # Target user must exist and be in same org
    target = db.get(User, payload.shared_with_user_id)
    if not target or target.organization_id != user.organization_id:
        db.close()
        raise HTTPException(status_code=404, detail="Target user not found in org")

    # Idempotent-ish share
    existing = (
        db.query(DocumentShare)
        .filter(
            DocumentShare.document_id == document_id,
            DocumentShare.shared_with_user_id == payload.shared_with_user_id
        )
        .first()
    )
    if existing:
        db.close()
        return {"status": "already_shared"}

    share = DocumentShare(
        id=str(uuid.uuid4()),
        document_id=document_id,
        shared_with_user_id=payload.shared_with_user_id,
        shared_by_user_id=user.id,
        can_read=True
    )
    db.add(share)
    db.commit()
    db.close()

    return {"status": "shared", "document_id": document_id, "shared_with": payload.shared_with_user_id}


@router.get("/{document_id}")
def get_document(document_id: str, user: User = Depends(get_current_user)):
    doc = get_document_or_404(document_id)

    # Enforce tenant isolation + role rules
    require_document_read_access(user, document_id)

    # Return basic metadata + a short preview
    fp = Path(doc.file_path)
    preview = ""
    if fp.exists():
        preview = fp.read_text(encoding="utf-8")[:600]

    return {
        "document_id": doc.id,
        "title": doc.title,
        "organization_id": doc.organization_id,
        "file_path": doc.file_path,
        "preview": preview
    }


@router.post("/upload")
async def upload_contract(file: UploadFile = File(...)):
    raise HTTPException(status_code=501, detail="Not implemented: upload + RBAC + tenant isolation")


@router.delete("/{document_id}")
def delete_document(document_id: str):
    raise HTTPException(status_code=501, detail="Not implemented: delete doc with RBAC")