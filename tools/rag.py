"""RAG (Retrieval-Augmented Generation) with ChromaDB."""
import logging
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
from pathlib import Path

logger = logging.getLogger("crawllama")


class RAGManager:
    """Manages document storage and semantic search with ChromaDB."""

    def __init__(
        self,
        persist_dir: str = "data/embeddings",
        collection_name: str = "web_documents"
    ):
        """
        Initialize RAG manager.

        Args:
            persist_dir: Directory to persist embeddings
            collection_name: Name of the collection
        """
        persist_path = Path(persist_dir)
        persist_path.mkdir(parents=True, exist_ok=True)

        try:
            self.client = chromadb.PersistentClient(path=str(persist_path))
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"RAG initialized: collection={collection_name}")

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise

    def add_documents(
        self,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None
    ) -> None:
        """
        Add documents to the collection.

        Args:
            texts: List of text documents
            metadatas: Optional metadata for each document
            ids: Optional custom IDs (auto-generated if not provided)
        """
        if not texts:
            logger.warning("No texts to add")
            return

        # Generate IDs if not provided
        if ids is None:
            import hashlib
            ids = [hashlib.md5(text.encode()).hexdigest()[:16] for text in texts]

        # Generate default metadata if not provided
        if metadatas is None:
            metadatas = [{"source": "unknown"} for _ in texts]

        try:
            self.collection.add(
                documents=texts,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"Added {len(texts)} documents to RAG")

        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            raise

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[dict] = None
    ) -> List[Dict]:
        """
        Semantic search for relevant documents.

        Args:
            query: Search query
            top_k: Number of results to return
            filter_metadata: Optional metadata filter

        Returns:
            List of result dictionaries with text, metadata, distance
        """
        logger.info(f"RAG search: '{query}' (top_k={top_k})")

        try:
            query_params = {
                "query_texts": [query],
                "n_results": top_k
            }

            if filter_metadata:
                query_params["where"] = filter_metadata

            results = self.collection.query(**query_params)

            # Format results
            formatted_results = []
            for i in range(len(results["documents"][0])):
                formatted_results.append({
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i],
                    "id": results["ids"][0][i]
                })

            logger.info(f"Found {len(formatted_results)} relevant documents")
            return formatted_results

        except Exception as e:
            logger.error(f"RAG search failed: {e}")
            return []

    def delete_documents(self, ids: List[str]) -> None:
        """
        Delete documents by ID.

        Args:
            ids: List of document IDs to delete
        """
        try:
            self.collection.delete(ids=ids)
            logger.info(f"Deleted {len(ids)} documents")

        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")

    def clear_collection(self) -> None:
        """Clear all documents from the collection."""
        try:
            self.client.delete_collection(self.collection.name)
            self.collection = self.client.create_collection(
                name=self.collection.name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("Collection cleared")

        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")

    def get_stats(self) -> Dict:
        """
        Get collection statistics.

        Returns:
            Dictionary with stats
        """
        try:
            count = self.collection.count()
            return {
                "name": self.collection.name,
                "document_count": count
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"name": self.collection.name, "document_count": 0}


def format_rag_results(results: List[Dict]) -> str:
    """
    Format RAG search results for LLM consumption.

    Args:
        results: List of search result dictionaries

    Returns:
        Formatted string
    """
    if not results:
        return "No relevant documents found."

    formatted = []
    for i, result in enumerate(results, 1):
        source = result["metadata"].get("source", "unknown")
        formatted.append(f"{i}. [Source: {source}]")
        formatted.append(f"   {result['text'][:300]}...")
        formatted.append(f"   Relevance: {1 - result['distance']:.2f}\n")

    return "\n".join(formatted)
