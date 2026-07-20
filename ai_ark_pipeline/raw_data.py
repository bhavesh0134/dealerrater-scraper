#!/usr/bin/env python3
"""
Shared helper for locating the raw AI-Ark JSON files that Claude Code
auto-saves to disk when an MCP tool result is too large to return inline.

Each Claude Code session gets its own session-id directory under
~/.claude/projects/<escaped-cwd>/<session-id>/tool-results/, so there is no
fixed path across runs. If --raw-dir isn't passed explicitly, we auto-detect
by finding the tool-results directory (under any session for this project)
containing the most recently modified mcp-ai-ark-* file — i.e. wherever the
current session has been saving its results.
"""
import glob
import os

PROJECTS_ROOT = os.path.expanduser(
    "~/.claude/projects/-Users-mac-Bhavesh-Claude-Projects"
)


def _auto_detect_raw_dir():
    candidates = glob.glob(os.path.join(PROJECTS_ROOT, "*", "tool-results"))
    best_dir, best_mtime = None, -1
    for d in candidates:
        matches = glob.glob(os.path.join(d, "mcp-ai-ark-*.txt"))
        if not matches:
            continue
        mtime = max(os.path.getmtime(p) for p in matches)
        if mtime > best_mtime:
            best_mtime = mtime
            best_dir = d
    return best_dir


def resolve_raw_dir(raw_dir=None):
    if raw_dir:
        return raw_dir
    detected = _auto_detect_raw_dir()
    if not detected:
        raise SystemExit(
            "No mcp-ai-ark-*.txt raw result files found anywhere under "
            f"{PROJECTS_ROOT}/*/tool-results/. Pass --raw-dir explicitly, "
            "or make at least one AI-Ark MCP call first so results get saved."
        )
    return detected


def email_finder_files(raw_dir=None):
    d = resolve_raw_dir(raw_dir)
    return glob.glob(os.path.join(d, "mcp-ai-ark-email_finder_results-*.txt"))


def company_search_files(raw_dir=None):
    d = resolve_raw_dir(raw_dir)
    return glob.glob(os.path.join(d, "mcp-ai-ark-company_search-*.txt"))
