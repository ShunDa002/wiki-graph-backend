from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Any

import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def parse_markdown(path: Path, wiki_dir: Path) -> dict[str, Any]:
    raw_text = path.read_text(encoding="utf-8", errors="replace")
    metadata: dict[str, Any] = {}
    body = raw_text

    if raw_text.startswith("---"):
        sections = raw_text.split("---", 2)
        if len(sections) == 3:
            try:
                loaded = yaml.safe_load(sections[1]) or {}
                metadata = loaded if isinstance(loaded, dict) else {}
                body = sections[2].strip()
            except yaml.YAMLError:
                metadata = {}
                body = raw_text

    tags = metadata.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    elif not isinstance(tags, list):
        tags = []

    title = metadata.get("title")
    if not isinstance(title, str) or not title.strip():
        title = path.stem.replace("-", " ")

    return {
        "path": path.relative_to(wiki_dir).as_posix(),
        "title": title.strip(),
        "description": str(metadata.get("description", "")),
        "tags": [str(tag) for tag in tags],
        "reviewed": bool(metadata.get("reviewed", False)),
        "confidence": str(metadata.get("confidence", "unknown")).lower(),
        "status": str(metadata.get("status", "unknown")).lower(),
        "body": body,
    }


class WikiStore:
    def __init__(self, wiki_dir: Path, source_folders: list[str]) -> None:
        self.wiki_dir = wiki_dir
        self.source_folders = source_folders
        self.documents: list[dict[str, Any]] = []
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix: Any = None
        self.concepts_docs: list[dict[str, Any]] = []
        self.sources_docs: list[dict[str, Any]] = []
        self._lock = RLock()
        self._loaded = False

    def diagnostics(self) -> dict[str, Any]:
        folder_counts: dict[str, int | None] = {}
        for folder in self.source_folders:
            folder_path = self.wiki_dir / folder
            folder_counts[folder] = (
                len(list(folder_path.rglob("*.md")))
                if folder_path.is_dir()
                else None
            )

        with self._lock:
            return {
                "directory": str(self.wiki_dir),
                "directory_exists": self.wiki_dir.is_dir(),
                "source_folders": list(self.source_folders),
                "folder_markdown_counts": folder_counts,
                "loaded": self._loaded,
                "document_count": len(self.documents),
                "concept_count": len(self.concepts_docs),
                "source_count": len(self.sources_docs),
            }

    def ensure_loaded(self) -> None:
        with self._lock:
            if self._loaded:
                return
            self.load()

    def load(self) -> None:
        documents_by_folder: dict[str, list[dict[str, Any]]] = {}

        for folder in self.source_folders:
            folder_path = self.wiki_dir / folder
            if not folder_path.is_dir():
                documents_by_folder[folder] = []
                continue

            resolved_folder = folder_path.resolve()
            documents_by_folder[folder] = [
                parse_markdown(path, self.wiki_dir)
                for path in sorted(folder_path.rglob("*.md"))
                if path.is_file()
                and path.resolve().is_relative_to(resolved_folder)
            ]

        documents = sorted(
            (
                document
                for folder_documents in documents_by_folder.values()
                for document in folder_documents
            ),
            key=lambda document: str(document.get("title", "")).casefold(),
        )

        if not documents:
            raise RuntimeError(
                "No Markdown files found in the configured chat source folders."
            )

        searchable_texts = [
            "\n".join(
                [
                    str(document["title"]),
                    str(document["description"]),
                    " ".join(document["tags"]),
                    str(document["body"]),
                ]
            )
            for document in documents
        ]

        vectorizer = TfidfVectorizer(
            analyzer="char",
            ngram_range=(2, 4),
            min_df=1,
            max_features=50_000,
        )
        matrix = vectorizer.fit_transform(searchable_texts)

        concepts_docs = documents_by_folder.get("concepts", [])
        sources_docs = documents_by_folder.get("sources", [])

        # Publish the new index atomically only after the complete load succeeds.
        with self._lock:
            self.documents = documents
            self.vectorizer = vectorizer
            self.matrix = matrix
            self.sources_docs = sources_docs
            self.concepts_docs = concepts_docs
            self._loaded = True

    def search(self, question: str, top_k: int = 4) -> list[dict[str, Any]]:
        self.ensure_loaded()

        cleaned_question = question.strip()
        if not cleaned_question or top_k <= 0:
            return []

        with self._lock:
            if self.matrix is None or self.vectorizer is None:
                raise RuntimeError("WikiStore index is unavailable after loading.")
            documents = list(self.documents)
            matrix = self.matrix
            vectorizer = self.vectorizer

        query_vector = vectorizer.transform([cleaned_question])
        scores = cosine_similarity(query_vector, matrix).flatten()
        question_lower = cleaned_question.lower()
        results: list[dict[str, Any]] = []

        for index, score in enumerate(scores):
            document = documents[index]
            final_score = float(score)
            title = str(document["title"]).lower()
            if title and title in question_lower:
                final_score += 0.20
            if document["reviewed"]:
                final_score += 0.08
            if document["confidence"] == "high":
                final_score += 0.05
            results.append({**document, "score": final_score})

        results.sort(key=lambda item: item["score"], reverse=True)
        return [result for result in results if result["score"] > 0.01][:top_k]
