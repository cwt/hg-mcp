"""Test to check which extensions are available on the system."""

import subprocess

import pytest


def test_list_available_extensions() -> None:
    """List all extensions available on the current system."""
    result = subprocess.run(
        ["hg", "config", "extensions"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        extensions = result.stdout.strip().split("\n")
        print(f"\n\nAvailable extensions ({len(extensions)}):")
        for ext in extensions:
            print(f"  - {ext}")
    else:
        pytest.skip("Could not query hg extensions")


def test_rebase_extension() -> None:
    """Check if rebase extension is available."""
    result = subprocess.run(
        ["hg", "help", "rebase"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip("rebase extension not available")
    assert "rebase" in result.stdout.lower()


def test_evolve_extension() -> None:
    """Check if evolve extension is available."""
    result = subprocess.run(
        ["hg", "help", "evolve"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip("evolve extension not available")
    assert "evolve" in result.stdout.lower()


def test_topic_extension() -> None:
    """Check if topic extension is available."""
    result = subprocess.run(
        ["hg", "help", "topic"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip("topic extension not available")
    assert "topic" in result.stdout.lower()


def test_hggit_extension() -> None:
    """Check if hg-git extension is available."""
    result = subprocess.run(
        ["hg", "help", "hggit"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip("hg-git extension not available")
    assert "hg-git" in result.stdout.lower() or "hggit" in result.stdout.lower()


def test_histedit_extension() -> None:
    """Check if histedit extension is available."""
    result = subprocess.run(
        ["hg", "help", "histedit"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip("histedit extension not available")
    assert "histedit" in result.stdout.lower()


def test_transplant_extension() -> None:
    """Check if transplant extension is available."""
    result = subprocess.run(
        ["hg", "help", "transplant"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip("transplant extension not available")
    assert "transplant" in result.stdout.lower()


def test_strip_extension() -> None:
    """Check if strip extension is available."""
    result = subprocess.run(
        ["hg", "help", "strip"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip("strip extension not available")
    assert "strip" in result.stdout.lower()
