"""Pytest fixtures for hg-mcp tests.

Provides isolated Mercurial repositories with controlled extension configurations.
"""

import subprocess
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test repositories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def hg_repo(temp_dir: Path) -> Generator[Path, None, None]:
    """Create an isolated Mercurial repository with NO extensions enabled.

    Returns the path to the repository root.
    """
    repo_path = temp_dir / "test-repo"
    repo_path.mkdir()

    # Initialize repository
    subprocess.run(
        ["hg", "init"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    # Create .hg/hgrc with NO extensions (explicitly disable all)
    hgrc = repo_path / ".hg" / "hgrc"
    hgrc.write_text(
        """[ui]
username = Test User <test@example.com>

[extensions]
# No extensions enabled - clean slate for testing
""",
        encoding="utf-8",
    )

    # Make an initial commit
    test_file = repo_path / "README.txt"
    test_file.write_text("Initial commit\n", encoding="utf-8")

    subprocess.run(
        ["hg", "add", "README.txt"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["hg", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    yield repo_path


@pytest.fixture
def hg_repo_with_commits(hg_repo: Path) -> Generator[Path, None, None]:
    """Create a repository with multiple commits for testing history operations.

    Creates a repo with 5 commits on default branch.
    """
    # Create additional commits
    for i in range(2, 6):
        test_file = hg_repo / f"file{i}.txt"
        test_file.write_text(f"Content {i}\n", encoding="utf-8")
        subprocess.run(
            ["hg", "add", f"file{i}.txt"],
            cwd=hg_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["hg", "commit", "-m", f"Commit {i}"],
            cwd=hg_repo,
            check=True,
            capture_output=True,
        )

    yield hg_repo


@pytest.fixture
def hg_repo_with_extensions(
    temp_dir: Path, extensions: list[str] | None = None
) -> Generator[Path, None, None]:
    """Create a Mercurial repository with specific extensions enabled.

    Args:
        temp_dir: Temporary directory fixture
        extensions: List of extension names to enable (e.g., ['rebase', 'evolve'])

    Usage:
        @pytest.mark.parametrize("extensions", [["rebase", "evolve"]])
        def test_something(hg_repo_with_extensions):
            ...
    """
    extensions = extensions or []
    repo_path = temp_dir / "test-repo"
    repo_path.mkdir()

    # Initialize repository
    subprocess.run(
        ["hg", "init"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    # Create .hg/hgrc with specified extensions
    hgrc = repo_path / ".hg" / "hgrc"
    ext_lines = "\n".join(f"{ext} =" for ext in extensions)
    hgrc.write_text(
        f"""[ui]
username = Test User <test@example.com>

[extensions]
{ext_lines}
""",
        encoding="utf-8",
    )

    # Make an initial commit
    test_file = repo_path / "README.txt"
    test_file.write_text("Initial commit\n", encoding="utf-8")

    subprocess.run(
        ["hg", "add", "README.txt"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["hg", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    yield repo_path


@pytest.fixture
def hg_repo_with_branches(
    hg_repo_with_commits: Path,
) -> Generator[Path, None, None]:
    """Create a repository with multiple branches for testing branch operations.

    Creates:
    - default branch with 5 commits
    - feature branch with 2 commits (branched from commit 2)
    """
    repo = hg_repo_with_commits

    # Update to revision 2 and create feature branch
    subprocess.run(
        ["hg", "update", "-r", "2"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["hg", "branch", "feature"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    # Add commits on feature branch
    for i in range(1, 3):
        test_file = repo / f"feature{i}.txt"
        test_file.write_text(f"Feature content {i}\n", encoding="utf-8")
        subprocess.run(
            ["hg", "add", f"feature{i}.txt"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["hg", "commit", "-m", f"Feature commit {i}"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

    # Return to default branch
    subprocess.run(
        ["hg", "update", "default"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    yield repo


@pytest.fixture
def hg_repo_with_bookmarks(
    hg_repo_with_commits: Path,
) -> Generator[Path, None, None]:
    """Create a repository with bookmarks for testing bookmark operations.

    Creates bookmarks at different revisions.
    """
    repo = hg_repo_with_commits

    # Create bookmarks at different revisions
    subprocess.run(
        ["hg", "bookmark", "stable", "-r", "3"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["hg", "bookmark", "latest", "-r", "tip"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    yield repo


@pytest.fixture
def hg_repo_with_tags(
    hg_repo_with_commits: Path,
) -> Generator[Path, None, None]:
    """Create a repository with tags for testing tag operations.

    Creates tags at different revisions.
    """
    repo = hg_repo_with_commits

    # Create tags at different revisions
    subprocess.run(
        ["hg", "tag", "-r", "2", "-m", "Add tag v1.0.0", "v1.0.0"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["hg", "tag", "-r", "tip", "-m", "Add tag v2.0.0", "v2.0.0"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    yield repo


@pytest.fixture
def hg_repo_with_remote(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a repository with a remote (another local repo as remote).

    Creates:
    - origin repo: bare-like repository
    - main repo: working repository with remote configured
    """
    # Create "remote" repository (acting as origin)
    origin_path = temp_dir / "origin"
    origin_path.mkdir()
    subprocess.run(
        ["hg", "init"],
        cwd=origin_path,
        check=True,
        capture_output=True,
    )

    # Create main repository
    main_path = temp_dir / "main"
    main_path.mkdir()
    subprocess.run(
        ["hg", "init"],
        cwd=main_path,
        check=True,
        capture_output=True,
    )

    # Configure remote
    hgrc = main_path / ".hg" / "hgrc"
    hgrc.write_text(
        f"""[ui]
username = Test User <test@example.com>

[paths]
default = {origin_path}
""",
        encoding="utf-8",
    )

    # Make initial commit and push
    test_file = main_path / "README.txt"
    test_file.write_text("Initial commit\n", encoding="utf-8")

    subprocess.run(
        ["hg", "add", "README.txt"],
        cwd=main_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["hg", "commit", "-m", "Initial commit"],
        cwd=main_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["hg", "push", "--create"],
        cwd=main_path,
        check=True,
        capture_output=True,
    )

    yield main_path
