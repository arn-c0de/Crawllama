"""RAG (Retrieval-Augmented Generation) with ChromaDB."""
import logging
from typing import List, Dict, Optional, Union
import chromadb
from chromadb.config import Settings
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import os

logger = logging.getLogger("crawllama")


class RAGManager:
    """Manages document storage and semantic search with ChromaDB."""

    def __init__(
        self,
        persist_dir: str = "data/embeddings",
        collection_name: str = "web_documents",
        batch_size: int = 100,
        max_workers: int = 4
    ):
        """
        Initialize RAG manager.

        Args:
            persist_dir: Directory to persist embeddings
            collection_name: Name of the collection
            batch_size: Batch size for processing documents
            max_workers: Max threads for parallel processing
        """
        persist_path = Path(persist_dir)
        persist_path.mkdir(parents=True, exist_ok=True)

        # Create models directory in project folder
        models_path = Path("data/models")
        models_path.mkdir(parents=True, exist_ok=True)

        # Set environment variable for ChromaDB to use project folder for models
        os.environ['CHROMA_CACHE_DIR'] = str(models_path.absolute())

        self.batch_size = batch_size
        self.max_workers = max_workers

        self.chroma_available = True
        self.fallback_mode = False
        
        try:
            # Create ChromaDB client with custom settings
            settings = Settings(
                persist_directory=str(persist_path),
                anonymized_telemetry=False
            )
            self.client = chromadb.PersistentClient(
                path=str(persist_path),
                settings=settings
            )
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"RAG initialized: collection={collection_name}, batch_size={batch_size}, models_dir={models_path}")

        except ImportError as e:
            logger.error(f"ChromaDB not available: {e}")
            self.chroma_available = False
            self.fallback_mode = True
            self.client = None
            self.collection = None
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e} - enabling fallback mode")
            self.chroma_available = False
            self.fallback_mode = True
            self.client = None
            self.collection = None

    def add_documents(
        self,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        use_batch: bool = True
    ) -> None:
        """
        Add documents to the collection with optional batch processing.

        Args:
            texts: List of text documents
            metadatas: Optional metadata for each document
            ids: Optional custom IDs (auto-generated if not provided)
            use_batch: Use batch processing for large document sets
        """
        if self.fallback_mode:
            logger.warning("ChromaDB not available - skipping document addition")
            return
            
        if not texts:
            logger.warning("No texts to add")
            return

        # Generate IDs if not provided
        if ids is None:
            ids = [hashlib.sha256(text.encode()).hexdigest() for text in texts]

        # Generate default metadata if not provided
        if metadatas is None:
            metadatas = [{"source": "unknown"} for _ in texts]

        try:
            # Use batch processing for large sets
            if use_batch and len(texts) > self.batch_size:
                logger.info(f"Using batch processing for {len(texts)} documents")
                self._add_documents_batch(texts, metadatas, ids)
            else:
                self.collection.add(
                    documents=texts,
                    metadatas=metadatas,
                    ids=ids
                )
                logger.info(f"Added {len(texts)} documents to RAG")

        except Exception as e:
            logger.error(f"Failed to add documents: {e} - enabling fallback mode")
            self.fallback_mode = True
            # Don't raise - graceful degradation

    def _add_documents_batch(
        self,
        texts: List[str],
        metadatas: List[dict],
        ids: List[str]
    ) -> None:
        """
        Add documents in batches for better memory management.

        Args:
            texts: List of text documents
            metadatas: List of metadata dicts
            ids: List of document IDs
        """
        total_docs = len(texts)
        added_count = 0

        for i in range(0, total_docs, self.batch_size):
            batch_end = min(i + self.batch_size, total_docs)
            batch_texts = texts[i:batch_end]
            batch_metadatas = metadatas[i:batch_end]
            batch_ids = ids[i:batch_end]

            try:
                self.collection.add(
                    documents=batch_texts,
                    metadatas=batch_metadatas,
                    ids=batch_ids
                )
                added_count += len(batch_texts)
                logger.info(f"Batch progress: {added_count}/{total_docs} documents")

            except Exception as e:
                logger.error(f"Failed to add batch {i}-{batch_end}: {e} - enabling fallback mode")
                self.fallback_mode = True
                return  # Stop processing but don't crash

        logger.info(f"Batch processing complete: {added_count} documents added")

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[dict] = None,
        min_relevance: float = 0.0
    ) -> List[Dict]:
        """
        Semantic search for relevant documents with relevance filtering.

        Args:
            query: Search query
            top_k: Number of results to return
            filter_metadata: Optional metadata filter
            min_relevance: Minimum relevance score (0-1, based on 1-distance)

        Returns:
            List of result dictionaries with text, metadata, distance, relevance
        """
        if self.fallback_mode:
            logger.warning("ChromaDB not available - returning empty search results")
            return []
            
        logger.info(f"RAG search: '{query}' (top_k={top_k}, min_relevance={min_relevance})")

        try:
            query_params = {
                "query_texts": [query],
                "n_results": top_k
            }

            if filter_metadata:
                query_params["where"] = filter_metadata

            results = self.collection.query(**query_params)

            # Format results with relevance score
            formatted_results = []
            for i in range(len(results["documents"][0])):
                distance = results["distances"][0][i]
                relevance = 1.0 - distance  # Convert distance to relevance score

                # Filter by minimum relevance
                if relevance >= min_relevance:
                    formatted_results.append({
                        "text": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": distance,
                        "relevance": relevance,
                        "id": results["ids"][0][i]
                    })

            logger.info(f"Found {len(formatted_results)} relevant documents (after filtering)")
            return formatted_results

        except Exception as e:
            logger.error(f"RAG search failed: {e} - enabling fallback mode")
            self.fallback_mode = True
            return []

    def multi_query_search(
        self,
        queries: List[str],
        top_k: int = 5,
        filter_metadata: Optional[dict] = None,
        deduplicate: bool = True
    ) -> List[Dict]:
        """
        Perform parallel searches for multiple queries and combine results.

        Args:
            queries: List of search queries
            top_k: Number of results per query
            filter_metadata: Optional metadata filter
            deduplicate: Remove duplicate documents from results

        Returns:
            Combined list of unique results sorted by relevance
        """
        logger.info(f"Multi-query search: {len(queries)} queries")

        all_results = []
        seen_ids = set()

        # Use ThreadPoolExecutor for parallel searches
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_query = {
                executor.submit(self.search, query, top_k, filter_metadata): query
                for query in queries
            }

            for future in as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    results = future.result()

                    if deduplicate:
                        for result in results:
                            doc_id = result["id"]
                            if doc_id not in seen_ids:
                                seen_ids.add(doc_id)
                                all_results.append(result)
                    else:
                        all_results.extend(results)

                except Exception as e:
                    logger.error(f"Search failed for query '{query}': {e}")

        # Sort by relevance
        all_results.sort(key=lambda x: x.get("relevance", 0), reverse=True)

        logger.info(f"Multi-query search complete: {len(all_results)} unique results")
        return all_results[:top_k]  # Return top results

    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        semantic_weight: float = 0.7
    ) -> List[Dict]:
        """
        Hybrid search combining semantic and keyword matching.

        Args:
            query: Search query
            top_k: Number of results to return
            semantic_weight: Weight for semantic search (0-1)

        Returns:
            Blended search results
        """
        logger.info(f"Hybrid search: '{query}' (semantic_weight={semantic_weight})")

        # Perform semantic search
        semantic_results = self.search(query, top_k=top_k * 2)

        # Generate query variants for better recall
        query_variants = [
            query,
            query.lower(),
            " ".join(query.split()[:3])  # First 3 words
        ]

        # Search with variants
        all_results = self.multi_query_search(
            queries=query_variants,
            top_k=top_k,
            deduplicate=True
        )

        return all_results[:top_k]

    def delete_documents(self, ids: List[str]) -> None:
        """
        Delete documents by ID.

        Args:
            ids: List of document IDs to delete
        """
        if self.fallback_mode:
            logger.warning("ChromaDB not available - skipping document deletion")
            return
            
        try:
            self.collection.delete(ids=ids)
            logger.info(f"Deleted {len(ids)} documents")

        except Exception as e:
            logger.error(f"Failed to delete documents: {e} - enabling fallback mode")
            self.fallback_mode = True

    def clear_collection(self) -> None:
        """Clear all documents from the collection."""
        if self.fallback_mode:
            logger.warning("ChromaDB not available - skipping collection clearing")
            return
            
        try:
            self.client.delete_collection(self.collection.name)
            self.collection = self.client.create_collection(
                name=self.collection.name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("Collection cleared")

        except Exception as e:
            logger.error(f"Failed to clear collection: {e} - enabling fallback mode")
            self.fallback_mode = True

    def get_stats(self) -> Dict:
        """
        Get collection statistics.

        Returns:
            Dictionary with stats
        """
        if self.fallback_mode:
            logger.warning("ChromaDB not available - returning fallback stats")
            return {"name": "fallback", "document_count": 0}
            
        try:
            count = self.collection.count()
            return {
                "name": self.collection.name,
                "document_count": count
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e} - enabling fallback mode")
            self.fallback_mode = True
            return {"name": "fallback", "document_count": 0}


def format_rag_results(results: List[Dict], max_length: int = 300) -> str:
    """
    Format RAG search results for LLM consumption.

    Args:
        results: List of search result dictionaries
        max_length: Maximum text length per result

    Returns:
        Formatted string
    """
    if not results:
        return "No relevant documents found."

    formatted = []
    for i, result in enumerate(results, 1):
        source = result["metadata"].get("source", "unknown")
        relevance = result.get("relevance", 1.0 - result.get("distance", 1.0))

        # Truncate text intelligently (try to break at sentence)
        text = result['text']
        if len(text) > max_length:
            text = text[:max_length]
            last_period = text.rfind('.')
            if last_period > max_length * 0.7:  # If period is reasonably close to end
                text = text[:last_period + 1]
            else:
                text += "..."

        formatted.append(f"{i}. [Source: {source}] (Relevance: {relevance:.2f})")
        formatted.append(f"   {text}\n")

    return "\n".join(formatted)
