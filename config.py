from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_GRAPH_SOURCE_FOLDERS = [
    "sources",
    "concepts",
    "decisions",
    "questions",
    "syntheses",
    "experiments",
    "projects",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    wiki_repo_dir: Path = Path("./data/source-repo")
    wiki_dir: Path = Path("./data/source-repo/wiki")
    graph_output_path: Path = Path("./data/generated/graph.json")

    # Only Markdown files below these wiki subfolders become graph nodes.
    # Root files such as wiki/index.md and wiki/log.md are therefore excluded.
    graph_source_folders: list[str] = DEFAULT_GRAPH_SOURCE_FOLDERS.copy()

    chat_source_folders: list[str] = ["sources", "concepts"]
    openrouter_model: str = "openrouter/free"
    chat_top_k: int = Field(4, ge=1, le=20)
    chat_max_page_chars: int = Field(12_000, ge=500, le=100_000)
    chat_max_total_context_chars: int = Field(35_000, ge=1_000, le=500_000)
    wiki_reload_secret_key: str | None = None

    graph_cache_enabled: bool = True
    graph_write_snapshot: bool = True
    graph_include_drafts: bool = True
    graph_include_deprecated: bool = False
    graph_excerpt_length: int = Field(240, ge=40, le=4000)
    graph_max_file_bytes: int = Field(2 * 1024 * 1024, ge=1024)
    graph_max_nodes: int = Field(10000, ge=1)
    graph_rebuild_secret_key: str | None = None
    frontend_origins: list[str] = ["http://localhost:3000"]

    @field_validator("graph_source_folders", "chat_source_folders")
    @classmethod
    def validate_graph_source_folders(cls, folders: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()

        for folder in folders:
            name = folder.strip().replace("\\", "/").strip("/")
            if not name or "/" in name or name in {".", ".."}:
                raise ValueError(
                    "GRAPH_SOURCE_FOLDERS entries must be direct folder names"
                )
            if name.casefold() not in seen:
                normalized.append(name)
                seen.add(name.casefold())

        if not normalized:
            raise ValueError("GRAPH_SOURCE_FOLDERS must contain at least one folder")

        return normalized

    @model_validator(mode="after")
    def validate_paths(self):
        self.wiki_repo_dir = self.wiki_repo_dir.resolve()
        self.wiki_dir = self.wiki_dir.resolve()
        self.graph_output_path = self.graph_output_path.resolve()

        if not self.wiki_dir.is_relative_to(self.wiki_repo_dir):
            raise ValueError("WIKI_DIR must be inside WIKI_REPO_DIR")
        if not self.wiki_dir.is_dir():
            raise ValueError(
                f"WIKI_DIR does not exist or is not a directory: {self.wiki_dir}"
            )
        if self.graph_output_path.is_relative_to(self.wiki_repo_dir):
            raise ValueError("GRAPH_OUTPUT_PATH must be outside WIKI_REPO_DIR")

        configured_folders = {
            *self.graph_source_folders,
            *self.chat_source_folders,
        }
        missing = [
            folder
            for folder in sorted(configured_folders)
            if not (self.wiki_dir / folder).is_dir()
        ]
        if missing:
            raise ValueError(
                "Configured graph source folders do not exist under WIKI_DIR: "
                + ", ".join(missing)
            )

        return self
