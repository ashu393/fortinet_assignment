from pathlib import Path
from app.db.session import SessionLocal
from app.db.models import Document, User

TECHCORP_DIR = Path("data/contracts/techcorp")
MEDICARE_DIR = Path("data/contracts/medicare")

def _title_from_filename(fp: Path) -> str:
    name = fp.stem  # without .txt
    # e.g. "TC-1042_Mutual-Non-Disclosure-Agreement"
    parts = name.split("_", 1)
    if len(parts) == 2:
        return parts[1].replace("-", " ")
    return name.replace("-", " ")

def seed_docs():
    db = SessionLocal()

    # choose an uploader (analyst) per org
    tech_uploader = db.get(User, "bob")
    med_uploader = db.get(User, "eve")
    if not tech_uploader or not med_uploader:
        db.close()
        raise RuntimeError("Seed users missing. Run init_db first.")

    # TechCorp docs
    for fp in TECHCORP_DIR.glob("*.txt"):
        doc_id = fp.name.split("_", 1)[0]  # TC-xxxx
        if not db.get(Document, doc_id):
            db.add(Document(
                id=doc_id,
                title=_title_from_filename(fp),
                file_path=str(fp),
                organization_id="techcorp",
                uploaded_by_user_id=tech_uploader.id
            ))

    # MediCare docs
    for fp in MEDICARE_DIR.glob("*.txt"):
        doc_id = fp.name.split("_", 1)[0]  # MC-xxxx
        if not db.get(Document, doc_id):
            db.add(Document(
                id=doc_id,
                title=_title_from_filename(fp),
                file_path=str(fp),
                organization_id="medicare",
                uploaded_by_user_id=med_uploader.id
            ))

    db.commit()
    db.close()
    print("✅ Documents seeded")

if __name__ == "__main__":
    seed_docs()