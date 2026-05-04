"""Codebase RAG - Semantic search over project files with local embeddings.

Provides 100% local retrieval-augmented generation for codebases:
- File indexing with Ollama embeddings or TF-IDF fallback
- Semantic chunking (functions, classes, modules)
- Cosine similarity search with confidence scores
- Integration with reasoning engine for transparent search rationale

Architecture:
    CodeChunker → EmbeddingProvider → VectorStore → CodebaseIndexer
"""

import os
import re
import json
import time
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from src.logger_config import get_logger

try:
    from src.reasoning import get_reasoning_engine, ReasoningType
    REASONING_AVAILABLE = True
except ImportError:
    REASONING_AVAILABLE = False

logger = get_logger("CodebaseRAG")

# Extensions to index
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".kt", ".go", ".rs",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".swift", ".rb", ".php",
    ".html", ".css", ".scss", ".sass", ".less",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml",
    ".md", ".rst", ".txt",
    ".sh", ".bat", ".ps1",
    ".sql",
}

# Extensions to skip
SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".obj", ".o",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".ico",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".ttf", ".woff", ".woff2", ".eot",
}

SKIP_DIRS = {
    ".git", ".svn", ".hg", ".autonomous", ".pytest_cache", ".mypy_cache",
    "__pycache__", "node_modules", "venv", ".venv", "env", ".env",
    "dist", "build", "target", ".idea", ".vscode", "coverage",
    ".tox", ".eggs", "*.egg-info",
}


class EmbeddingBackend(Enum):
    OLLAMA = "ollama"
    TFIDF = "tfidf"
    NONE = "none"


@dataclass
class CodeChunk:
    """A semantic chunk of code with metadata."""
    id: str
    file_path: str
    content: str
    chunk_type: str  # "function", "class", "module", "section"
    start_line: int
    end_line: int
    language: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """A single semantic search result."""
    chunk: CodeChunk
    score: float
    rank: int
    reasoning: str = ""


class CodeChunker:
    """Splits source files into semantic chunks."""

    # Language-specific patterns
    PATTERNS = {
        "python": {
            "function": r"^[ \t]*(?:async\s+)?def\s+(\w+)",
            "class": r"^[ \t]*class\s+(\w+)",
            "comment": r"^[ \t]*#",
        },
        "javascript": {
            "function": r"^[ \t]*(?:async\s+)?(?:function\s+)?(\w+)\s*\(|^[ \t]*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\(?.*\)?\s*=>)",
            "class": r"^[ \t]*class\s+(\w+)",
            "comment": r"^[ \t]*//",
        },
        "java": {
            "function": r"^[ \t]*(?:public|private|protected)?\s*(?:static\s+)?(?:\w+\s+)?(\w+)\s*\(",
            "class": r"^[ \t]*(?:public\s+)?class\s+(\w+)",
            "comment": r"^[ \t]*//",
        },
        "go": {
            "function": r"^[ \t]*func\s+(?:\(.*\)\s+)?(\w+)",
            "class": r"^[ \t]*type\s+(\w+)\s+struct",
            "comment": r"^[ \t]*//",
        },
        "rust": {
            "function": r"^[ \t]*(?:pub\s+)?fn\s+(\w+)",
            "class": r"^[ \t]*(?:pub\s+)?(?:struct|enum|trait)\s+(\w+)",
            "comment": r"^[ \t]*//",
        },
        "default": {
            "function": r"^[ \t]*(?:function|def|func|fn|void|int|String|bool)\s+(\w+)",
            "class": r"^[ \t]*(?:class|struct|interface|trait|enum)\s+(\w+)",
            "comment": r"^[ \t]*(?:#|//|--)",
        },
    }

    def __init__(self, max_chunk_size: int = 2000, overlap: int = 200):
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap

    def get_language(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        mapping = {
            ".py": "python", ".js": "javascript", ".ts": "javascript",
            ".jsx": "javascript", ".tsx": "javascript", ".java": "java",
            ".kt": "kotlin", ".go": "go", ".rs": "rust",
            ".c": "c", ".cpp": "cpp", ".h": "c", ".hpp": "cpp",
            ".cs": "csharp", ".swift": "swift", ".rb": "ruby",
            ".php": "php", ".html": "html", ".css": "css",
            ".scss": "css", ".sass": "css", ".less": "css",
            ".json": "json", ".yaml": "yaml", ".yml": "yaml",
            ".toml": "toml", ".md": "markdown", ".sql": "sql",
            ".sh": "shell", ".bat": "batch", ".ps1": "powershell",
        }
        return mapping.get(ext, "default")

    def chunk_file(self, file_path: str, content: str) -> List[CodeChunk]:
        """Split a file into semantic chunks."""
        language = self.get_language(file_path)
        lines = content.split("\n")
        chunks = []
        chunk_id_base = hashlib.md5(file_path.encode()).hexdigest()[:8]

        if language in ("json", "yaml", "toml", "markdown", "txt"):
            # For config/docs: treat whole file as one chunk
            chunks.append(CodeChunk(
                id=f"{chunk_id_base}_0",
                file_path=file_path,
                content=content,
                chunk_type="module",
                start_line=1,
                end_line=len(lines),
                language=language,
            ))
            return chunks

        patterns = self.PATTERNS.get(language, self.PATTERNS["default"])
        current_chunk_lines = []
        current_chunk_start = 0
        current_type = "module"
        current_name = ""
        chunk_idx = 0

        def flush_chunk(end_line: int):
            nonlocal chunk_idx
            if not current_chunk_lines:
                return
            chunk_content = "\n".join(current_chunk_lines)
            if len(chunk_content) < 10:
                return
            chunks.append(CodeChunk(
                id=f"{chunk_id_base}_{chunk_idx}",
                file_path=file_path,
                content=chunk_content,
                chunk_type=current_type,
                start_line=current_chunk_start + 1,
                end_line=end_line,
                language=language,
                metadata={"name": current_name} if current_name else {},
            ))
            chunk_idx += 1

        for i, line in enumerate(lines):
            # Detect new function/class boundary
            new_type = None
            new_name = ""

            for pattern_type, pattern in patterns.items():
                if pattern_type == "comment":
                    continue
                match = re.match(pattern, line)
                if match:
                    new_type = pattern_type
                    new_name = next((g for g in match.groups() if g), "")
                    break

            if new_type and current_chunk_lines:
                # Flush current chunk before starting new one
                flush_chunk(i)
                current_chunk_lines = []
                current_chunk_start = i
                current_type = new_type
                current_name = new_name

            current_chunk_lines.append(line)

            # Force flush if chunk gets too large
            chunk_text = "\n".join(current_chunk_lines)
            if len(chunk_text) > self.max_chunk_size:
                flush_chunk(i)
                # Start overlap
                overlap_lines = current_chunk_lines[-self.overlap:]
                current_chunk_lines = overlap_lines
                current_chunk_start = i - len(overlap_lines) + 1
                current_type = "section"
                current_name = ""

        # Flush remaining
        flush_chunk(len(lines))

        # If no chunks were created (e.g., very small file), use whole file
        if not chunks:
            chunks.append(CodeChunk(
                id=f"{chunk_id_base}_0",
                file_path=file_path,
                content=content,
                chunk_type="module",
                start_line=1,
                end_line=len(lines),
                language=language,
            ))

        return chunks


class EmbeddingProvider:
    """Provides text embeddings via Ollama or TF-IDF fallback."""

    def __init__(self, ollama_host: str = "http://localhost:11434", model: str = "qwen3:8b-gpu"):
        self.host = ollama_host
        self.model = model
        self.backend: EmbeddingBackend = EmbeddingBackend.NONE
        self._tfidf = None
        self._tfidf_vectors = None
        self._tfidf_chunks = []
        self._detect_backend()

    def _detect_backend(self):
        """Detect available embedding backend."""
        try:
            import httpx
            response = httpx.get(f"{self.host}/api/tags", timeout=5.0)
            if response.status_code == 200:
                self.backend = EmbeddingBackend.OLLAMA
                logger.info("Embedding backend: Ollama")
                return
        except Exception:
            pass

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.backend = EmbeddingBackend.TFIDF
            logger.info("Embedding backend: TF-IDF (fallback)")
        except ImportError:
            logger.warning("No embedding backend available")

    def _get_ollama_embedding(self, text: str) -> Optional[np.ndarray]:
        """Get embedding from Ollama."""
        try:
            import httpx
            response = httpx.post(
                f"{self.host}/api/embeddings",
                json={"model": self.model, "prompt": text[:4000]},
                timeout=30.0,
            )
            if response.status_code == 200:
                data = response.json()
                embedding = data.get("embedding", [])
                if embedding:
                    return np.array(embedding, dtype=np.float32)
        except Exception as e:
            logger.debug(f"Ollama embedding failed: {e}")
        return None

    def embed(self, texts: List[str]) -> np.ndarray:
        """Embed a list of texts into vectors."""
        if self.backend == EmbeddingBackend.OLLAMA:
            vectors = []
            for text in texts:
                vec = self._get_ollama_embedding(text)
                if vec is not None:
                    vectors.append(vec)
                else:
                    # Fallback to zero vector of standard size
                    vectors.append(np.zeros(4096, dtype=np.float32))
            return np.array(vectors)

        elif self.backend == EmbeddingBackend.TFIDF:
            from sklearn.feature_extraction.text import TfidfVectorizer
            if self._tfidf is None:
                self._tfidf = TfidfVectorizer(max_features=2000, stop_words="english")
                self._tfidf.fit(texts)
            return self._tfidf.transform(texts).toarray().astype(np.float32)

        else:
            # No backend: use simple word count vectors
            return self._simple_embed(texts)

    def embed_query(self, text: str) -> np.ndarray:
        """Embed a single query text."""
        if self.backend == EmbeddingBackend.OLLAMA:
            vec = self._get_ollama_embedding(text)
            if vec is not None:
                return vec
            return np.zeros(4096, dtype=np.float32)
        elif self.backend == EmbeddingBackend.TFIDF:
            if self._tfidf is None:
                return np.zeros(2000, dtype=np.float32)
            return self._tfidf.transform([text]).toarray().astype(np.float32)[0]
        else:
            return self._simple_embed([text])[0]

    def _simple_embed(self, texts: List[str]) -> np.ndarray:
        """Simple bag-of-words embedding as ultimate fallback."""
        vocab = set()
        tokenized = []
        for text in texts:
            tokens = re.findall(r"\b\w+\b", text.lower())
            tokenized.append(tokens)
            vocab.update(tokens)
        vocab = sorted(vocab)
        vocab_idx = {w: i for i, w in enumerate(vocab)}
        vectors = np.zeros((len(texts), len(vocab)), dtype=np.float32)
        for i, tokens in enumerate(tokenized):
            for token in tokens:
                if token in vocab_idx:
                    vectors[i, vocab_idx[token]] += 1
        # Normalize
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return vectors / norms

    def fit_tfidf(self, texts: List[str]):
        """Fit TF-IDF on a corpus (for search-time queries)."""
        if self.backend == EmbeddingBackend.TFIDF:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self._tfidf = TfidfVectorizer(max_features=2000, stop_words="english")
            self._tfidf.fit(texts)


class VectorStore:
    """Simple numpy-based vector store with cosine similarity."""

    def __init__(self):
        self.vectors: Optional[np.ndarray] = None
        self.chunks: List[CodeChunk] = []
        self.dimension: int = 0

    def add(self, chunks: List[CodeChunk], vectors: np.ndarray):
        """Add chunks with their vectors."""
        if len(chunks) != len(vectors):
            raise ValueError("Chunks and vectors must have same length")
        self.chunks = chunks
        self.vectors = vectors
        self.dimension = vectors.shape[1] if len(vectors) > 0 else 0

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> List[Tuple[CodeChunk, float]]:
        """Search for top-k most similar chunks."""
        if self.vectors is None or len(self.chunks) == 0:
            return []

        # Cosine similarity
        query_norm = np.linalg.norm(query_vector)
        if query_norm == 0:
            return []
        query_unit = query_vector / query_norm

        vectors_norm = np.linalg.norm(self.vectors, axis=1, keepdims=True)
        vectors_norm[vectors_norm == 0] = 1
        vectors_unit = self.vectors / vectors_norm

        similarities = np.dot(vectors_unit, query_unit)

        # Get top-k
        top_indices = np.argsort(similarities)[::-1][:top_k]
        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score > 0.01:  # Filter near-zero similarity
                results.append((self.chunks[idx], score))
        return results

    def clear(self):
        """Clear all vectors and chunks."""
        self.vectors = None
        self.chunks = []
        self.dimension = 0

    def __len__(self) -> int:
        return len(self.chunks)


class CodebaseIndexer:
    """Main RAG indexer for a codebase."""

    def __init__(self, project_path: str, ollama_host: str = "http://localhost:11434", model: str = "qwen3:8b-gpu"):
        self.project_path = Path(project_path).resolve()
        self.chunker = CodeChunker()
        self.embedder = EmbeddingProvider(ollama_host=ollama_host, model=model)
        self.store = VectorStore()
        self._indexed = False
        self._index_time = 0.0

    def index(self, force: bool = False) -> Dict[str, Any]:
        """Index all code files in the project."""
        if self._indexed and not force:
            return {"status": "already_indexed", "chunks": len(self.store)}

        start = time.time()
        all_chunks: List[CodeChunk] = []

        # Collect files
        files_to_index = []
        for root, dirs, files in os.walk(self.project_path):
            # Skip directories
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            for filename in files:
                ext = Path(filename).suffix.lower()
                if ext in CODE_EXTENSIONS:
                    file_path = Path(root) / filename
                    try:
                        rel_path = file_path.relative_to(self.project_path)
                        files_to_index.append((str(rel_path), str(file_path)))
                    except ValueError:
                        continue

        # Chunk files
        for rel_path, abs_path in files_to_index:
            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if len(content) > 500_000:  # Skip huge files
                    logger.warning(f"Skipping large file: {rel_path}")
                    continue
                chunks = self.chunker.chunk_file(str(rel_path), content)
                all_chunks.extend(chunks)
            except Exception as e:
                logger.debug(f"Failed to chunk {rel_path}: {e}")

        if not all_chunks:
            return {"status": "no_files", "chunks": 0, "files": 0}

        # Embed chunks
        texts = [c.content for c in all_chunks]
        vectors = self.embedder.embed(texts)

        # Fit TF-IDF if using that backend
        if self.embedder.backend == EmbeddingBackend.TFIDF:
            self.embedder.fit_tfidf(texts)

        self.store.add(all_chunks, vectors)
        self._indexed = True
        self._index_time = time.time() - start

        result = {
            "status": "success",
            "chunks": len(all_chunks),
            "files": len(files_to_index),
            "backend": self.embedder.backend.value,
            "duration": round(self._index_time, 2),
        }
        logger.info(f"Indexed {result['files']} files into {result['chunks']} chunks ({result['duration']}s)")
        return result

    def search(self, query: str, top_k: int = 5) -> List[SearchResult]:
        """Semantic search over the codebase."""
        if not self._indexed:
            self.index()

        if not self.store.chunks:
            return []

        query_vector = self.embedder.embed_query(query)
        raw_results = self.store.search(query_vector, top_k=top_k * 2)

        # Deduplicate by file (keep best chunk per file)
        seen_files = set()
        deduped = []
        for chunk, score in raw_results:
            if chunk.file_path not in seen_files:
                seen_files.add(chunk.file_path)
                deduped.append((chunk, score))
            if len(deduped) >= top_k:
                break

        # Build results with reasoning
        results = []
        for rank, (chunk, score) in enumerate(deduped, 1):
            reasoning = self._build_result_reasoning(chunk, score, query)
            results.append(SearchResult(
                chunk=chunk,
                score=score,
                rank=rank,
                reasoning=reasoning,
            ))

        return results

    def _build_result_reasoning(self, chunk: CodeChunk, score: float, query: str) -> str:
        """Build a human-readable reasoning for why this result is relevant."""
        parts = []

        if chunk.chunk_type == "function":
            name = chunk.metadata.get("name", "unknown")
            parts.append(f"Function '{name}' matches query semantics")
        elif chunk.chunk_type == "class":
            name = chunk.metadata.get("name", "unknown")
            parts.append(f"Class '{name}' matches query semantics")
        else:
            parts.append(f"File section matches query semantics")

        if score > 0.8:
            parts.append("Very high relevance")
        elif score > 0.6:
            parts.append("High relevance")
        elif score > 0.4:
            parts.append("Moderate relevance")
        else:
            parts.append("Low relevance")

        parts.append(f"Language: {chunk.language}")
        return "; ".join(parts)

    def get_context_for_prompt(self, query: str, top_k: int = 3, max_chars: int = 4000) -> str:
        """Get formatted context string for LLM prompting."""
        results = self.search(query, top_k=top_k)
        if not results:
            return ""

        context_parts = ["# Relevant Code Context\n"]
        total_chars = len(context_parts[0])

        for result in results:
            chunk = result.chunk
            header = f"\n## {chunk.file_path} (lines {chunk.start_line}-{chunk.end_line}, relevance: {result.score:.2f})\n```\n"
            content = chunk.content[:1500]  # Limit per chunk
            footer = "\n```\n"

            part = header + content + footer
            if total_chars + len(part) > max_chars:
                break
            context_parts.append(part)
            total_chars += len(part)

        return "".join(context_parts)

    def get_stats(self) -> Dict[str, Any]:
        """Get indexer statistics."""
        return {
            "indexed": self._indexed,
            "chunks": len(self.store),
            "backend": self.embedder.backend.value,
            "index_time": round(self._index_time, 2),
            "project_path": str(self.project_path),
        }

    def clear(self):
        """Clear the index."""
        self.store.clear()
        self._indexed = False
        self._index_time = 0.0


# Global indexer cache
_indexers: Dict[str, CodebaseIndexer] = {}


def get_codebase_indexer(project_path: str, ollama_host: str = "http://localhost:11434", model: str = "qwen3:8b-gpu") -> CodebaseIndexer:
    """Get or create a codebase indexer for a project path."""
    cache_key = f"{project_path}:{model}"
    if cache_key not in _indexers:
        _indexers[cache_key] = CodebaseIndexer(project_path, ollama_host, model)
    return _indexers[cache_key]


def reset_codebase_indexers():
    """Reset all cached indexers."""
    global _indexers
    _indexers = {}
