from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ChromaDB
    chroma_dir: str = "chroma_db"
    collection_name: str = "cs_knowledge_base"

    # Database - individual PostgreSQL settings
    pghost: str = "localhost"
    pgport: str = "5432"
    pgdatabase: str = "cs_support"
    pguser: str = "postgres"
    pgpassword: str = "postgres"

    # Alternative: full DATABASE_URL (if provided, takes precedence)
    database_url: str = ""

    # OpenAI
    openai_api_key: str

    # LLM
    model_name: str = "gpt-4o-mini"
    temperature: float = 0.1

    # Retrieval and embedding
    embedding_model: str = "text-embedding-3-small"
    top_k: int = 3  # number of chunks to retrieve during the RAG
    chunk_size: int = 400  # number of tokens to chunk the documents
    knowledge_base_dir: str = "cs_knowledge_base"

    @computed_field
    @property
    def computed_database_url(self) -> str:
        """
        Return DATABASE_URL if provided, otherwise construct from individual pg* fields
        """
        if self.database_url:
            return self.database_url
        return f"postgresql://{self.pguser}:{self.pgpassword}@{self.pghost}:{self.pgport}/{self.pgdatabase}"


settings = Settings()