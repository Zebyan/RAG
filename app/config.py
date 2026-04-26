from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "citydock-rag-mvp"
    app_version: str = "0.1.0"
    rag_api_key: str = "test-api-key"
    database_path: str = "./data/app.db"

    vector_store: str = "memory"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "rag_chunks"

    chroma_persist_path: str = "./data/chroma"
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384

    url_fetch_timeout_seconds: float = 60.0

    llm_provider: str = "none"
    anthropic_api_key: str | None = None
    webhook_secret: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
