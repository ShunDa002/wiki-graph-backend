from pathlib import Path

import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

APP_ROOT = Path(__file__).resolve().parent
SOURCE_REPO_DIR = APP_ROOT / "data" / "source-repo"
SOURCES_DIR = SOURCE_REPO_DIR / "wiki" / "sources"
CONCEPTS_DIR = SOURCE_REPO_DIR / "wiki" / "concepts"


def parse_markdown(path: Path) -> dict:
    raw_text = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    metadata = {}
    body = raw_text

    if raw_text.startswith("---"):
        sections = raw_text.split("---", 2)

        if len(sections) == 3:
            try:
                metadata = yaml.safe_load(sections[1]) or {}
                body = sections[2].strip()
            except yaml.YAMLError:
                metadata = {}
                body = raw_text

    tags = metadata.get("tags", [])

    if isinstance(tags, str):
        tags = [tags]

    return {
        "path": path.relative_to(path.parent).as_posix(),
        "title": metadata.get(
            "title",
            path.stem.replace("-", " "),
        ),
        "description": metadata.get(
            "description",
            "",
        ),
        "tags": tags,
        "reviewed": bool(metadata.get("reviewed", False)),
        "confidence": metadata.get(
            "confidence",
            "unknown",
        ),
        "status": metadata.get(
            "status",
            "unknown",
        ),
        "body": body,
    }


class WikiStore:
    def __init__(self) -> None:
        self.documents = []
        self.vectorizer = None
        self.matrix = None
        self.concepts_docs = []
        self.sources_docs = []

    def load(self) -> None:
        self.sources_docs = [parse_markdown(path) for path in SOURCES_DIR.rglob("*.md")]

        self.concepts_docs = [
            parse_markdown(path) for path in CONCEPTS_DIR.rglob("*.md")
        ]

        self.documents = sorted(
            self.sources_docs + self.concepts_docs,
            key=lambda document: str(document.get("title", "")).casefold(),
        )

        if not self.documents:
            raise RuntimeError("No Markdown files found in the wiki/ directory.")

        searchable_texts = []

        for document in self.documents:
            searchable_texts.append(
                "\n".join(
                    [
                        str(document["title"]),
                        str(document["description"]),
                        " ".join(document["tags"]),
                        document["body"],
                    ]
                )
            )

        self.vectorizer = TfidfVectorizer(
            analyzer="char",
            ngram_range=(2, 4),
            min_df=1,
            max_features=50_000,
        )

        self.matrix = self.vectorizer.fit_transform(searchable_texts)

    def search(
        self,
        question: str,
        top_k: int = 4,
    ) -> list:
        if self.matrix is None:
            raise RuntimeError("WikiStore not loaded.")

        query_vector = self.vectorizer.transform([question])

        scores = cosine_similarity(
            query_vector,
            self.matrix,
        ).flatten()

        results = []

        for index, score in enumerate(scores):
            document = self.documents[index]
            final_score = float(score)

            title = str(document["title"]).lower()

            if title in question.lower():
                final_score += 0.20

            if document["reviewed"]:
                final_score += 0.08

            if document["confidence"] == "high":
                final_score += 0.05

            results.append(
                {
                    **document,
                    "score": final_score,
                }
            )

        results.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        return [result for result in results if result["score"] > 0.01][:top_k]
