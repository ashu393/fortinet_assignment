from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_env: str = "local"

    # JWT
    jwt_secret: str
    jwt_alg: str = "HS256"
    access_token_expires_min: int = 120

    # DB
    database_url: str = "sqlite:///./data/app.db"

    # Vector DB
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "contracts_chunks"

    # LLM
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # Embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Guardrails defaults
    default_hallucination_threshold: float = 0.70
    default_require_citations: bool = True
    default_pii_redaction: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
