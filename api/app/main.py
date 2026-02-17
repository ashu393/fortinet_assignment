from fastapi import FastAPI
from app.routers import auth, documents, chat, admin, search, mcp

app = FastAPI(title="Contract Intelligence API (PoC)")

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(mcp.router, prefix="/mcp", tags=["mcp"])

@app.get("/health")
def health():
    return {"status": "ok"}
