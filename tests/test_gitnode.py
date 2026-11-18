"""Tests for companion gitnode enrichment and agent instructions."""

import json
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from unittest.mock import patch

import pytest

from hg_mcp.helpers import (
    JSON_SUPPORTED_COMMANDS,
    _enrich_data_with_gitnode,
    _find_hg_dir,
    _format_json_output,
    _is_git_backed_repo,
    _is_git_dir,
    _is_git_remote_value,
    _is_hex_node,
    _load_git_mapfile,
    _parse_hg_json_output,
    _resolve_gitnode_for_item,
    _resolve_store_hg_dir,
    run_hg_command,
)
from hg_mcp.server import mcp
from hg_mcp.tools import (
    hg_bookmarks,
    hg_commit,
    hg_git,
    hg_heads,
    hg_identify,
    hg_incoming,
    hg_log,
    hg_outgoing,
    hg_stack,
    hg_status,
    hg_tags,
)


def _extract_text(result: str | Sequence[object]) -> str:
    """Extract text from MCP tool output."""
    if isinstance(result, str):
        return result
    return "\n".join(str(getattr(item, "text", item)) for item in result)


def _extract_json_list(result: str | Sequence[object]) -> list[dict[str, object]]:
    """Parse JSON list returned by an MCP tool."""
    parsed = json.loads(_extract_text(result))
    assert isinstance(parsed, list)
    return parsed


def _has_git_and_hggit() -> bool:
    """Return True if git CLI and hg-git extension are available."""
    if shutil.which("git") is None:
        return False
    res = subprocess.run(
        ["hg", "--config", "extensions.hggit=", "help", "hggit"],
        capture_output=True,
        text=True,
    )
    return res.returncode == 0


class TestGitnodeHelpers:
    """Unit tests for git-mapfile loading and JSON gitnode enrichment."""

    def test_is_hex_node(self) -> None:
        """Validate 40-char hexadecimal node check."""
        assert _is_hex_node("a" * 40) is True
        assert _is_hex_node("0123456789abcdefABCDEF" + "0" * 18) is True
        assert _is_hex_node("a" * 39) is False
        assert _is_hex_node("g" * 40) is False
        assert _is_hex_node(123) is False

    def test_is_git_dir_variants(self, temp_dir: Path) -> None:
        """Detect working tree .git, bare Git repos, and exclude Hg repos."""
        plain_dir = temp_dir / "plain"
        plain_dir.mkdir()
        assert _is_git_dir(plain_dir) is False
        assert _is_git_dir(temp_dir / "missing") is False

        hg_and_git = temp_dir / "hg_intree"
        hg_and_git.mkdir()
        (hg_and_git / ".hg").mkdir()
        (hg_and_git / ".git").mkdir()
        assert _is_git_dir(hg_and_git) is False

        worktree_git = temp_dir / "worktree_git"
        worktree_git.mkdir()
        (worktree_git / ".git").mkdir()
        assert _is_git_dir(worktree_git) is True

        bare_git = temp_dir / "bare.git"
        bare_git.mkdir()
        (bare_git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (bare_git / "objects").mkdir()
        (bare_git / "refs").mkdir()
        assert _is_git_dir(bare_git) is True

    def test_is_git_remote_value(self, temp_dir: Path) -> None:
        """Recognize Git URLs, SCP SSH paths, and local Git directories."""
        assert _is_git_remote_value("") is False
        assert _is_git_remote_value("   ") is False
        assert _is_git_remote_value("git+https://example.com/repo") is True
        assert _is_git_remote_value("https://github.com/user/repo") is True
        assert _is_git_remote_value("https://gitlab.com/user/repo.git") is True
        assert _is_git_remote_value("git@github.com:user/repo") is True
        assert _is_git_remote_value("https://hg.example.com/repo") is False

        local_git = temp_dir / "upstream"
        local_git.mkdir()
        (local_git / ".git").mkdir()
        assert _is_git_remote_value(str(local_git)) is True
        assert _is_git_remote_value(f"file://{local_git}") is True

        local_hg = temp_dir / "hg_upstream"
        local_hg.mkdir()
        (local_hg / ".hg").mkdir()
        assert _is_git_remote_value(str(local_hg)) is False

    def test_find_hg_dir_and_shared_store(self, temp_dir: Path) -> None:
        """Locate .hg from nested paths and resolve .hg/sharedpath."""
        assert _find_hg_dir(temp_dir) is None

        src_repo = temp_dir / "source"
        src_hg = src_repo / ".hg"
        src_hg.mkdir(parents=True)
        nested = src_repo / "a" / "b"
        nested.mkdir(parents=True)
        assert _find_hg_dir(nested) == src_hg

        shared_abs = temp_dir / "shared_abs"
        shared_abs_hg = shared_abs / ".hg"
        shared_abs_hg.mkdir(parents=True)
        (shared_abs_hg / "sharedpath").write_text(str(src_hg), encoding="utf-8")
        assert _resolve_store_hg_dir(shared_abs_hg) == src_hg

        shared_rel = temp_dir / "shared_rel"
        shared_rel_hg = shared_rel / ".hg"
        shared_rel_hg.mkdir(parents=True)
        (shared_rel_hg / "sharedpath").write_text("../source/.hg", encoding="utf-8")
        assert _resolve_store_hg_dir(shared_rel_hg) == src_hg.resolve()

        empty_shared = temp_dir / "empty_shared"
        empty_shared_hg = empty_shared / ".hg"
        empty_shared_hg.mkdir(parents=True)
        (empty_shared_hg / "sharedpath").write_text("", encoding="utf-8")
        assert _resolve_store_hg_dir(empty_shared_hg) == empty_shared_hg

    def test_is_git_backed_repo_and_mapfile_loading(
        self, hg_repo: Path, temp_dir: Path
    ) -> None:
        """Detect Git-backed repos via files/hgrc and parse git-mapfile safely."""
        assert _is_git_backed_repo(None) == (False, None)
        assert _is_git_backed_repo(temp_dir) == (False, None)
        assert _is_git_backed_repo(hg_repo) == (False, None)

        hg_hash = "1" * 40
        git_hash_old = "a" * 40
        git_hash_new = "b" * 40
        mapfile = hg_repo / ".hg" / "git-mapfile"
        mapfile.write_text(
            f"# comment\n\nbad line\n"
            f"{git_hash_old} {hg_hash}\n"
            f"{git_hash_new} {hg_hash}\n",
            encoding="utf-8",
        )
        is_backed, found_map = _is_git_backed_repo(hg_repo)
        assert is_backed is True
        assert found_map == mapfile

        loaded = _load_git_mapfile(found_map)
        assert loaded == {hg_hash: git_hash_new}
        assert _load_git_mapfile(None) == {}
        assert _load_git_mapfile(temp_dir / "missing") == {}

        # Remote-only detection via .hg/hgrc [paths]
        remote_only = temp_dir / "remote_only"
        (remote_only / ".hg").mkdir(parents=True)
        (remote_only / ".hg" / "hgrc").write_text(
            "[paths]\ndefault = git+https://example.com/repo.git\n",
            encoding="utf-8",
        )
        assert _is_git_backed_repo(remote_only) == (True, None)

    def test_resolve_gitnode_edge_cases(self) -> None:
        """Handle mapped, unmapped, null, working-dir, merge, and incoming items."""
        hg_a = "1" * 40
        git_a = "a" * 40
        hg_unmapped = "2" * 40
        git_map = {hg_a: git_a}

        assert _resolve_gitnode_for_item({"node": hg_a}, git_map) == git_a
        assert _resolve_gitnode_for_item({"node": hg_unmapped}, git_map) is None
        assert _resolve_gitnode_for_item({"node": "0" * 40}, git_map) is None
        assert _resolve_gitnode_for_item({"node": "not-a-node"}, git_map) is None

        # Working-directory virtual node (ffff...) resolves single mapped parent
        assert (
            _resolve_gitnode_for_item(
                {"node": "f" * 40, "parents": [hg_a]},
                git_map,
            )
            == git_a
        )
        # Unmapped single parent -> None
        assert (
            _resolve_gitnode_for_item(
                {"node": "f" * 40, "parents": [hg_unmapped]},
                git_map,
            )
            is None
        )
        # Empty repo (0000... parent) -> None
        assert (
            _resolve_gitnode_for_item(
                {"node": "f" * 40, "parents": ["0" * 40]},
                git_map,
            )
            is None
        )
        # Uncommitted merge (2 parents) -> None
        assert (
            _resolve_gitnode_for_item(
                {"node": "f" * 40, "parents": [hg_a, hg_unmapped]},
                git_map,
            )
            is None
        )
        # Incoming from Git remote uses node directly as gitnode
        incoming_git = "c" * 40
        assert (
            _resolve_gitnode_for_item(
                {"node": incoming_git},
                git_map,
                incoming_from_git=True,
            )
            == incoming_git
        )

    def test_enrich_data_with_gitnode_skips_non_node_entries(self) -> None:
        """Ensure status/config items without 'node' are untouched."""
        git_map = {"1" * 40: "a" * 40}
        status_items: list[dict[str, object]] = [{"path": "README.md", "status": "M"}]
        _enrich_data_with_gitnode(status_items, git_map)
        assert status_items == [{"path": "README.md", "status": "M"}]

        single_dict: dict[str, object] = {"node": "1" * 40}
        _enrich_data_with_gitnode(single_dict, git_map)
        assert single_dict["gitnode"] == "a" * 40

    def test_parse_and_format_incoming_outgoing_output(
        self, hg_repo: Path, temp_dir: Path
    ) -> None:
        """Strip preamble and enrich incoming/outgoing JSON payloads."""
        hg_a = "1" * 40
        git_a = "a" * 40
        (hg_repo / ".hg" / "git-mapfile").write_text(
            f"{git_a} {hg_a}\n", encoding="utf-8"
        )

        outgoing_raw = (
            f"comparing with {temp_dir}/remote\n"
            "searching for changes\n"
            f'[{{"node":"{hg_a}","rev":1}}]'
        )
        formatted_out = _format_json_output(outgoing_raw, "outgoing", hg_repo)
        parsed_out = json.loads(formatted_out)
        assert parsed_out == [{"node": hg_a, "rev": 1, "gitnode": git_a}]

        incoming_git_node = "d" * 40
        incoming_raw = (
            "comparing with https://github.com/user/repo.git\n"
            f'[{{"node":"{incoming_git_node}","rev":2}}]'
        )
        formatted_in = _format_json_output(incoming_raw, "incoming", hg_repo)
        parsed_in = json.loads(formatted_in)
        assert parsed_in == [
            {"node": incoming_git_node, "rev": 2, "gitnode": incoming_git_node}
        ]

        # Non-JSON output falls back unchanged
        assert _parse_hg_json_output("plain text", "log") == (None, "", None)
        assert _format_json_output("plain text", "log", hg_repo) == "plain text"

    def test_stack_in_json_supported_commands(self) -> None:
        """Verify stack is registered in JSON_SUPPORTED_COMMANDS."""
        assert "stack" in JSON_SUPPORTED_COMMANDS


class TestGitnodeTools:
    """Integration tests verifying companion gitnode across MCP tools."""

    @pytest.mark.asyncio
    async def test_plain_hg_repo_omits_gitnode(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Plain Mercurial repos should NOT include gitnode."""
        log_entries = _extract_json_list(
            await hg_log(repo_path=str(hg_repo_with_commits), limit=3)
        )
        assert len(log_entries) == 3
        for entry in log_entries:
            assert "node" in entry
            assert "gitnode" not in entry

        id_entries = _extract_json_list(
            await hg_identify(repo_path=str(hg_repo_with_commits))
        )
        assert "gitnode" not in id_entries[0]

    @pytest.mark.asyncio
    async def test_mapped_and_unexported_commits_in_git_backed_repo(
        self, hg_repo_with_commits: Path
    ) -> None:
        """Mapped commits return 40-char gitnode; unexported commits return null."""
        # Create bookmark and tag on existing commits
        subprocess.run(
            ["hg", "bookmark", "main.git", "-r", "3"],
            cwd=hg_repo_with_commits,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["hg", "tag", "-r", "2", "-m", "Add v1.0.0", "v1.0.0"],
            cwd=hg_repo_with_commits,
            check=True,
            capture_output=True,
        )

        # Read real 40-char hg nodes for all commits except tip (unexported)
        nodes_out = subprocess.run(
            ["hg", "log", "-T", "{rev}:{node}\n"],
            cwd=hg_repo_with_commits,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        rev_to_hg: dict[int, str] = {}
        for line in nodes_out.splitlines():
            rev_str, hg_node = line.split(":", 1)
            rev_to_hg[int(rev_str)] = hg_node

        tip_rev = max(rev_to_hg)
        map_lines: list[str] = []
        rev_to_git: dict[int, str] = {}
        for rev, hg_node in rev_to_hg.items():
            if rev == tip_rev:
                continue  # Leave tip unexported to test gitnode: null
            git_sha = f"{rev:040x}"
            rev_to_git[rev] = git_sha
            map_lines.append(f"{git_sha} {hg_node}")

        (hg_repo_with_commits / ".hg" / "git-mapfile").write_text(
            "\n".join(map_lines) + "\n", encoding="utf-8"
        )

        # 1. hg_log: tip has gitnode=None (null), earlier commits have git SHA
        log_entries = _extract_json_list(
            await hg_log(repo_path=str(hg_repo_with_commits), limit=10)
        )
        assert log_entries[0]["rev"] == tip_rev
        assert log_entries[0]["gitnode"] is None
        assert log_entries[1]["gitnode"] == rev_to_git[log_entries[1]["rev"]]  # type: ignore[index]

        # Verify serialized JSON explicitly contains null (not "")
        raw_log_text = _extract_text(
            await hg_log(repo_path=str(hg_repo_with_commits), limit=1)
        )
        assert '"gitnode":null' in raw_log_text

        # 2. hg_heads: tip is unexported head -> gitnode is null
        heads_entries = _extract_json_list(
            await hg_heads(repo_path=str(hg_repo_with_commits))
        )
        assert heads_entries[0]["gitnode"] is None

        # 3. hg_bookmarks: main.git points to rev 3 (mapped)
        bm_entries = _extract_json_list(
            await hg_bookmarks(repo_path=str(hg_repo_with_commits))
        )
        assert bm_entries[0]["bookmark"] == "main.git"
        assert bm_entries[0]["gitnode"] == rev_to_git[3]

        # 4. hg_tags: v1.0.0 points to rev 2 (mapped), tip points to tip_rev (null)
        tag_entries = _extract_json_list(
            await hg_tags(repo_path=str(hg_repo_with_commits))
        )
        tags_by_name = {str(entry["tag"]): entry for entry in tag_entries}
        assert tags_by_name["v1.0.0"]["gitnode"] == rev_to_git[2]
        assert tags_by_name["tip"]["gitnode"] is None

        # 5. hg_identify with revision (mapped vs unexported)
        id_rev3 = _extract_json_list(
            await hg_identify(repo_path=str(hg_repo_with_commits), revision="3")
        )
        assert id_rev3[0]["gitnode"] == rev_to_git[3]

        # 6. hg_identify without revision (working dir on mapped commit 3)
        subprocess.run(
            ["hg", "update", "-r", "3"],
            cwd=hg_repo_with_commits,
            check=True,
            capture_output=True,
        )
        id_wdir = _extract_json_list(
            await hg_identify(repo_path=str(hg_repo_with_commits))
        )
        assert id_wdir[0]["node"] == "f" * 40
        assert id_wdir[0]["gitnode"] == rev_to_git[3]

        # 7. hg_status should NOT add gitnode to file entries
        (hg_repo_with_commits / "README.txt").write_text("modified\n", encoding="utf-8")
        status_entries = _extract_json_list(
            await hg_status(repo_path=str(hg_repo_with_commits))
        )
        assert "gitnode" not in status_entries[0]

    @pytest.mark.asyncio
    async def test_hg_stack_enriches_gitnode_when_json(self, hg_repo: Path) -> None:
        """Verify hg_stack enriches stack entries with gitnode via run_hg_command."""
        hg_node = "3" * 40
        git_node = "e" * 40
        (hg_repo / ".hg" / "git-mapfile").write_text(
            f"{git_node} {hg_node}\n", encoding="utf-8"
        )
        mock_stack = json.dumps(
            [{"desc": "wip", "isentry": True, "node": hg_node, "stack_index": 1}]
        )
        with patch(
            "hg_mcp.tools.hggit.run_hg_command",
            return_value=_format_json_output(mock_stack, "stack", hg_repo),
        ):
            entries = _extract_json_list(await hg_stack(str(hg_repo)))
        assert entries[0]["node"] == hg_node
        assert entries[0]["gitnode"] == git_node

    @pytest.mark.asyncio
    async def test_real_hggit_end_to_end(self, temp_dir: Path) -> None:
        """End-to-end test cloning a real Git repo with hg-git."""
        if not _has_git_and_hggit():
            pytest.skip("git or hg-git extension not available")

        git_repo = temp_dir / "upstream_git"
        git_repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=git_repo, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=git_repo,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=git_repo,
            check=True,
        )
        (git_repo / "file.txt").write_text("v1\n", encoding="utf-8")
        subprocess.run(["git", "add", "file.txt"], cwd=git_repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "git commit 1"], cwd=git_repo, check=True
        )
        git_sha1 = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        hg_clone_dir = temp_dir / "hg_clone"
        subprocess.run(
            [
                "hg",
                "--config",
                "extensions.hggit=",
                "clone",
                "-q",
                str(git_repo),
                str(hg_clone_dir),
            ],
            check=True,
            capture_output=True,
        )
        # Ensure hggit is enabled in local repo hgrc regardless of global config
        with (hg_clone_dir / ".hg" / "hgrc").open("a", encoding="utf-8") as handle:
            handle.write(
                "\n[ui]\nusername = Test User <test@example.com>\n\n"
                "[extensions]\nhggit =\n"
            )

        # Verify hg_log, hg_identify, hg_heads, hg_bookmarks all return git_sha1
        log_entries = _extract_json_list(await hg_log(repo_path=str(hg_clone_dir)))
        assert log_entries[0]["gitnode"] == git_sha1

        id_entries = _extract_json_list(await hg_identify(repo_path=str(hg_clone_dir)))
        assert id_entries[0]["gitnode"] == git_sha1

        heads_entries = _extract_json_list(await hg_heads(repo_path=str(hg_clone_dir)))
        assert heads_entries[0]["gitnode"] == git_sha1

        # Create local commit via hg_commit (auto-runs gexport) and test hg_outgoing
        # before upstream diverges
        (hg_clone_dir / "local.txt").write_text("local\n", encoding="utf-8")
        subprocess.run(
            ["hg", "add", "local.txt"],
            cwd=hg_clone_dir,
            check=True,
            capture_output=True,
        )
        commit_res = await hg_commit("local hg commit", repo_path=str(hg_clone_dir))
        assert "Bookmarks exported" in commit_res

        outgoing_entries = _extract_json_list(
            await hg_outgoing(repo_path=str(hg_clone_dir))
        )
        assert len(outgoing_entries) == 1
        assert outgoing_entries[0]["gitnode"] is not None
        assert _is_hex_node(outgoing_entries[0]["gitnode"])

        # Add upstream Git commit and test hg_incoming
        (git_repo / "file.txt").write_text("v2\n", encoding="utf-8")
        subprocess.run(
            ["git", "commit", "-q", "-a", "-m", "git commit 2"],
            cwd=git_repo,
            check=True,
        )
        git_sha2 = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        incoming_entries = _extract_json_list(
            await hg_incoming(repo_path=str(hg_clone_dir))
        )
        assert incoming_entries[0]["node"] == git_sha2
        assert incoming_entries[0]["gitnode"] == git_sha2

        # Verify explicit custom -T template is NOT coerced to JSON
        raw_desc = await run_hg_command(
            ["log", "-l", "1", "-T", "{desc}"], cwd=hg_clone_dir
        )
        assert raw_desc == "local hg commit"


class TestGitnodeAgentInstructions:
    """Verify server instructions and tool docs teach agents about gitnode."""

    def test_server_instructions_document_node_vs_gitnode(self) -> None:
        """Server instructions explain node vs gitnode and hg_log usage."""
        instructions = mcp.instructions or ""
        assert "gitnode" in instructions
        assert "gitnode(" in instructions
        assert "null" in instructions
        assert "repo_path" in instructions and "limit" in instructions

    def test_node_tool_docstrings_document_gitnode(self) -> None:
        """Tools returning 40-char node explain companion gitnode."""
        assert "limit" in (hg_log.__doc__ or "")
        for tool_fn in (
            hg_log,
            hg_identify,
            hg_heads,
            hg_bookmarks,
            hg_tags,
            hg_incoming,
            hg_outgoing,
            hg_stack,
            hg_git,
        ):
            doc = tool_fn.__doc__ or ""
            assert (
                "gitnode" in doc
            ), f"{tool_fn.__name__} docstring should mention gitnode"
