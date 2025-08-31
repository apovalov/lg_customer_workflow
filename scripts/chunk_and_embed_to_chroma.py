import logging
from pathlib import Path
from langchain.docstore.document import Document
from langchain.text_splitter import Language, RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from config import settings
from clients.vector_db import vector_db_client

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize splitter and embedder
md_separators = RecursiveCharacterTextSplitter.get_separators_for_language(
    Language.MARKDOWN
)
splitter = rec_splitter_with_md = RecursiveCharacterTextSplitter(
    separators=md_separators,
    chunk_size=settings.chunk_size,
)
embeddings = OpenAIEmbeddings(
    model=settings.embedding_model, api_key=settings.openai_api_key
)


def main():
    documents = []
    knowledge_base_path = Path(settings.knowledge_base_dir)

    # Recursively find all .md files
    md_files = list(knowledge_base_path.rglob("*.md"))
    logger.info(f"Found {len(md_files)} markdown files in {settings.knowledge_base_dir}")
    logger.info(f"Chunking up files in {settings.knowledge_base_dir}...")

    file_count = 0
    chunk_total = 0

    for filepath in md_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()

            # Get relative path for better metadata
            relative_path = filepath.relative_to(knowledge_base_path)

            chunks = splitter.split_text(text)
            for chunk_index, chunk in enumerate(chunks):
                doc = Document(
                    page_content=chunk,
                    metadata={
                        "filename": str(relative_path),
                        "chunk_index": chunk_index,
                        "category": relative_path.parent.name if relative_path.parent.name != "." else "general"
                    },
                )
                documents.append(doc)
            file_count += 1
            chunk_total += len(chunks)
            logger.info(f"Processed {relative_path}: {len(chunks)} chunks")

        except Exception as e:
            logger.error(f"Error processing {filepath}: {e}")

    logger.info(f"Total files processed: {file_count}")
    logger.info(f"Total chunks created: {chunk_total}")

    # Embed and store in Chroma
    if documents:
        logger.info("Embedding and storing documents in ChromaDB...")
        vector_db_client.embed_documents(documents)
        logger.info(
            f"Loaded {len(documents)} chunks into ChromaDB at '{settings.chroma_dir}'"
        )
    else:
        logger.warning("No markdown files found or no chunks created.")


if __name__ == "__main__":
    main()
