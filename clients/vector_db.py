from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.docstore.document import Document
import logging

from config import settings

logger = logging.getLogger(__name__)


class VectorDBClient:
    def __init__(self, chroma_dir: str, collection_name: str):
        self.chroma_dir = chroma_dir
        self.collection_name = collection_name
        self.embeddings = OpenAIEmbeddings(
            model=settings.embedding_model, api_key=settings.openai_api_key
        )
        self.db = Chroma(
            persist_directory=self.chroma_dir,
            collection_name=self.collection_name,
            embedding_function=self.embeddings,
        )

    def embed_documents(self, documents: list[Document]) -> None:
        """Create ChromaDB collection from documents."""
        try:
            self.db = Chroma.from_documents(
                documents,
                self.embeddings,
                collection_name=self.collection_name,
                persist_directory=self.chroma_dir,
            )
        except Exception as e:
            logger.error(f"Failed to embed documents: {e}")
            raise

    def similarity_search(self, query: str, k: int = settings.top_k) -> list[Document]:
        """Search for similar documents."""
        if not self.db:
            raise ValueError("No documents embedded yet or collection not created")
        return self.db.similarity_search(query, k=k)


vector_db_client = VectorDBClient(
    chroma_dir=settings.chroma_dir,
    collection_name=settings.collection_name,
)
