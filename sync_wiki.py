import shutil
import subprocess
from pathlib import Path
from dotenv import dotenv_values

APP_ROOT = Path(__file__).resolve().parent
DATA_DIR = APP_ROOT / "data"
SOURCE_REPO_DIR = DATA_DIR / "source-repo"

# Read the .env file into a dictionary without loading it into os.environ
config = dotenv_values(".env")
# Access only the specific variable you want
REPOSITORY_URL = config.get("REPOSITORY_URL")


def run_git(*args: str) -> None:
    command = ["git", *args]

    subprocess.run(
        command,
        check=True,
        cwd=APP_ROOT,
    )


def clone_repository() -> None:
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_git(
        "clone",
        "--depth",
        "1",
        "--filter=blob:none",
        REPOSITORY_URL,
        str(SOURCE_REPO_DIR),
    )


def update_repository() -> None:
    subprocess.run(
        [
            "git",
            "fetch",
            "origin",
            "main",
            "--depth",
            "1",
        ],
        check=True,
        cwd=SOURCE_REPO_DIR,
    )

    subprocess.run(
        [
            "git",
            "reset",
            "--hard",
            "origin/main",
        ],
        check=True,
        cwd=SOURCE_REPO_DIR,
    )


def sync_repository() -> None:
    git_directory = SOURCE_REPO_DIR / ".git"

    if not git_directory.exists():
        if SOURCE_REPO_DIR.exists():
            shutil.rmtree(SOURCE_REPO_DIR)

        clone_repository()
    else:
        update_repository()

    wiki_directory = SOURCE_REPO_DIR / "wiki"

    if not wiki_directory.exists():
        raise RuntimeError("Sync failed: 'wiki' directory not found in the repository.")

    print(f"Wiki was synced successfully: {wiki_directory}")


if __name__ == "__main__":
    sync_repository()
