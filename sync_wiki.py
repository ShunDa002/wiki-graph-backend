import shutil
import subprocess
from pathlib import Path

from dotenv import dotenv_values

APP_ROOT = Path(__file__).resolve().parent
DATA_DIR = APP_ROOT / "data"
SOURCE_REPO_DIR = DATA_DIR / "source-repo"
ENV_FILE = APP_ROOT / ".env"

TARGET_DIRECTORY = "wiki"
TARGET_BRANCH = "main"


config = dotenv_values(ENV_FILE)
REPOSITORY_URL = config.get("REPOSITORY_URL")

if not REPOSITORY_URL:
    raise RuntimeError(f"REPOSITORY_URL is missing or empty in {ENV_FILE}")


def run_git(
    *args: str,
    cwd: Path = APP_ROOT,
) -> None:
    subprocess.run(
        ["git", *args],
        check=True,
        cwd=cwd,
    )


def is_git_repository(directory: Path) -> bool:
    if not directory.is_dir():
        return False

    result = subprocess.run(
        [
            "git",
            "rev-parse",
            "--is-inside-work-tree",
        ],
        cwd=directory,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        text=True,
    )

    return result.returncode == 0


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
        "--sparse",
        "--branch",
        TARGET_BRANCH,
        REPOSITORY_URL,
        str(SOURCE_REPO_DIR),
    )

    run_git(
        "sparse-checkout",
        "set",
        TARGET_DIRECTORY,
        cwd=SOURCE_REPO_DIR,
    )


def update_repository() -> None:
    run_git(
        "fetch",
        "origin",
        TARGET_BRANCH,
        "--depth",
        "1",
        cwd=SOURCE_REPO_DIR,
    )

    run_git(
        "reset",
        "--hard",
        f"origin/{TARGET_BRANCH}",
        cwd=SOURCE_REPO_DIR,
    )

    # Reapply the sparse-checkout configuration in case files outside
    # the sparse definition have appeared in the working tree.
    run_git(
        "sparse-checkout",
        "reapply",
        cwd=SOURCE_REPO_DIR,
    )


def sync_repository() -> None:
    if not is_git_repository(SOURCE_REPO_DIR):
        if SOURCE_REPO_DIR.exists():
            shutil.rmtree(SOURCE_REPO_DIR)

        clone_repository()
    else:
        update_repository()

    wiki_directory = SOURCE_REPO_DIR / TARGET_DIRECTORY

    if not wiki_directory.is_dir():
        raise RuntimeError(
            f"Sync failed: '{TARGET_DIRECTORY}' directory "
            "was not found in the repository."
        )

    print(f"Wiki was synced successfully: {wiki_directory}")


if __name__ == "__main__":
    sync_repository()
