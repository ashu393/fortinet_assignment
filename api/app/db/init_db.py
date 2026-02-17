import json
import uuid
from pathlib import Path
from passlib.context import CryptContext

from app.db.session import engine, SessionLocal
from app.db.models import Base, Organization, User, GuardrailSettings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SEED_PATH = Path("data/seed/seed.json")

def create_tables():
    Base.metadata.create_all(bind=engine)

def seed():
    if not SEED_PATH.exists():
        raise FileNotFoundError(f"Seed file not found: {SEED_PATH}")

    payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    db = SessionLocal()

    # Orgs
    for org in payload["organizations"]:
        if not db.get(Organization, org["id"]):
            db.add(Organization(id=org["id"], name=org["name"]))

    db.commit()

    # Guardrails defaults per org
    for org in payload["organizations"]:
        existing = db.get(GuardrailSettings, org["id"])
        if not existing:
            db.add(GuardrailSettings(
                organization_id=org["id"],
                hallucination_confidence_threshold=0.70,
                pii_redaction_enabled=True,
                require_citations=True,
                blocked_keywords_csv=""
            ))
    db.commit()

    # Users
    for u in payload["users"]:
        if not db.get(User, u["id"]):
            db.add(User(
                id=u["id"],
                email=u["email"],
                role=u["role"],
                organization_id=u["organization_id"],
                password_hash=pwd_context.hash(u["password"])
            ))
    db.commit()
    db.close()

def main():
    create_tables()
    seed()
    print("✅ DB initialized + seeded")

if __name__ == "__main__":
    main()