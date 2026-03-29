"""
UCW Enrichment Pipeline — Smart classification for v0.5.0

Replaces the keyword-matching in ucw_bridge.py with real classification:
  - Project extraction from file paths and explicit mentions
  - Domain classification with signal density scoring
  - Intent classification with confidence
  - Noise-stripped summaries
  - Typed concept extraction
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Project path patterns
# ---------------------------------------------------------------------------

_PROJECT_PATH_RE = re.compile(
    r"/projects/"
    r"(?:products|apps|core|portfolio|decks|tools|libs|infra)"
    r"/([a-zA-Z0-9_-]+)",
)

_CWD_PROJECT_RE = re.compile(
    r"(?:/projects/[^/]+/|/home/[^/]+/)"
    r"([a-zA-Z0-9_-]+)",
)

# Canonical project names (lowered key -> display name)
_KNOWN_PROJECTS: dict[str, str] = {
    "friendlyface": "friendlyface",
    "careercoach": "careercoach",
    "careercoachantigravity": "careercoach",
    "ucw": "ucw",
    "os-app": "os-app",
    "osapp": "os-app",
    "meta-vengine": "meta-vengine",
    "metavengine": "meta-vengine",
    "researchgravity": "researchgravity",
    "openviking": "openviking",
    "frontier-alpha": "frontier-alpha",
    "frontieralpha": "frontier-alpha",
    "pageindex": "pageindex",
    "dicoangelo": "dicoangelo",
    "agent-core": "agent-core",
    "agentcore": "agent-core",
    "sovereign-deck": "sovereign-deck",
    "enterprise-deck": "enterprise-deck",
}

# Regex that matches any known project name as a whole word (case-insensitive)
_PROJECT_MENTION_RE = re.compile(
    r"\b("
    + "|".join(re.escape(k) for k in _KNOWN_PROJECTS)
    + r")\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Domain keywords
# ---------------------------------------------------------------------------

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "authentication": [
        "auth", "login", "password", "token", "jwt", "oauth", "session",
    ],
    "deployment": [
        "deploy", "vercel", "railway", "docker", "ci/cd", "pipeline", "build",
    ],
    "frontend": [
        "react", "component", "css", "tailwind", "vite", "ui", "layout",
        "responsive",
    ],
    "backend": [
        "api", "endpoint", "server", "route", "middleware", "fastapi",
        "express",
    ],
    "database": [
        "sql", "sqlite", "postgres", "migration", "schema", "query", "table",
    ],
    "testing": [
        "test", "assert", "mock", "fixture", "pytest", "coverage", "spec",
    ],
    "devops": [
        "git", "branch", "merge", "commit", "pr", "ci", "workflow", "action",
    ],
    "research": [
        "paper", "arxiv", "thesis", "finding", "hypothesis", "literature",
    ],
    "design": [
        "figma", "brand", "color", "typography", "logo", "palette",
    ],
}

# ---------------------------------------------------------------------------
# Intent signals
# ---------------------------------------------------------------------------

_INTENT_SIGNALS: dict[str, list[str]] = {
    "build": ["create", "add", "implement", "write", "new file"],
    "debug": ["fix", "bug", "error", "broken", "failing", "traceback"],
    "refactor": ["refactor", "clean up", "rename", "move", "extract"],
    "research": ["how", "what", "why", "explain", "understand"],
    "review": ["review", "check", "audit", "look at"],
    "deploy": ["deploy", "push", "release", "publish", "ship"],
    "configure": ["config", "setup", "install", "env", "settings"],
    "plan": ["plan", "design", "architect", "prd", "roadmap", "strategy"],
}

# ---------------------------------------------------------------------------
# Noise-stripping patterns for summary extraction
# ---------------------------------------------------------------------------

_SYSTEM_REMINDER_RE = re.compile(
    r"<system-reminder>.*?</system-reminder>", re.DOTALL,
)
_XML_TAG_RE = re.compile(r"<[^>]+>")
_JSON_BLOB_RE = re.compile(r"\{[^{}]{100,}\}")
_CODE_BLOCK_RE = re.compile(r"```[^`]*```", re.DOTALL)
_TOOL_USE_BLOCK_RE = re.compile(
    r"<(?:function_calls|antml:invoke|antml:parameter)[^>]*>.*?"
    r"</(?:function_calls|antml:invoke|antml:parameter)>",
    re.DOTALL,
)
_FILE_LISTING_RE = re.compile(r"(?:^[ \t]*(?:/[\w./-]+|[\w./-]+\.\w+)\s*$\n?){3,}", re.MULTILINE)

# ---------------------------------------------------------------------------
# Concept extraction patterns
# ---------------------------------------------------------------------------

_TECH_TERMS: set[str] = {
    "react", "python", "sqlite", "tailwind", "vite", "next.js", "nextjs",
    "typescript", "javascript", "node", "fastapi", "express", "docker",
    "vercel", "railway", "postgres", "redis", "supabase", "prisma",
    "hatch", "ruff", "pytest", "click", "rich", "pydantic", "flask",
    "django", "vue", "svelte", "angular", "webpack", "esbuild",
    "graphql", "rest", "grpc", "mcp", "json-rpc",
}

_FILE_RE = re.compile(r"\b([\w./-]*\w+\.(?:py|tsx?|jsx?|md|json|toml|yaml|yml|sql|sh|css|html))\b")
_COMMAND_RE = re.compile(
    r"\b(git|npm|pip|ucw|ruff|pytest|python3?|node|docker|vercel|railway|cargo|bun)\b",
)
_ERROR_RE = re.compile(r"\b([A-Z]\w*(?:Error|Exception|Warning|Fault))\b")


# ===================================================================
# Public API
# ===================================================================


def classify_topic(content: str, metadata: dict[str, Any] | None = None) -> str:
    """Extract project or domain topic from conversation content.

    Priority: file paths > metadata cwd > explicit mentions > domain > fallback.
    """
    if not content and not metadata:
        return "general"

    # 1. Project from file paths in content
    if content:
        m = _PROJECT_PATH_RE.search(content)
        if m:
            name = m.group(1).lower()
            return _KNOWN_PROJECTS.get(name, name)

    # 2. Project from metadata (cwd / project_dir)
    if metadata:
        for key in ("cwd", "project_dir"):
            val = metadata.get(key, "")
            if val:
                m = _PROJECT_PATH_RE.search(val)
                if m:
                    name = m.group(1).lower()
                    return _KNOWN_PROJECTS.get(name, name)
                m = _CWD_PROJECT_RE.search(val)
                if m:
                    name = m.group(1).lower()
                    return _KNOWN_PROJECTS.get(name, name)

    # 3. Explicit project mentions
    if content:
        m = _PROJECT_MENTION_RE.search(content)
        if m:
            name = m.group(1).lower()
            return _KNOWN_PROJECTS.get(name, name)

    # 4. Domain classification
    if content:
        cl = content.lower()
        best_domain = "general"
        best_score = 0
        for domain, keywords in _DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in cl)
            if score > best_score:
                best_domain = domain
                best_score = score
        if best_score > 0:
            return best_domain

    # 5. Fallback
    return "general"


def classify_intent(content: str) -> tuple[str, float]:
    """Return (intent_label, confidence) based on signal density."""
    if not content:
        return ("discuss", 0.0)

    cl = content.lower()
    word_count = max(len(cl.split()), 1)

    # Check for error tracebacks explicitly (strong debug signal)
    has_traceback = "traceback" in cl or "Traceback" in content

    scores: dict[str, int] = {}
    for intent, signals in _INTENT_SIGNALS.items():
        score = sum(1 for s in signals if s in cl)
        if intent == "debug" and has_traceback:
            score += 2
        scores[intent] = score

    best_intent = max(scores, key=lambda k: scores[k])
    best_score = scores[best_intent]

    if best_score == 0:
        return ("discuss", 0.1)

    # Confidence: ratio of matched signals to total signals for that intent,
    # boosted by density relative to content length.
    max_possible = len(_INTENT_SIGNALS[best_intent])
    ratio = best_score / max_possible
    # Density bonus: short content with many signals is high confidence
    density = min(best_score / (word_count / 10), 1.0)
    confidence = round(min((ratio + density) / 2, 1.0), 2)
    confidence = max(confidence, 0.1)

    return (best_intent, confidence)


def extract_summary(content: str, max_length: int = 200) -> str:
    """Extract a clean human-readable summary, stripping noise."""
    if not content:
        return ""

    text = content
    # Strip system-reminder blocks
    text = _SYSTEM_REMINDER_RE.sub("", text)
    # Strip tool-use blocks
    text = _TOOL_USE_BLOCK_RE.sub("", text)
    # Strip code blocks longer than 3 lines
    def _strip_long_code(m: re.Match) -> str:
        block = m.group(0)
        if block.count("\n") > 3:
            return ""
        return block
    text = _CODE_BLOCK_RE.sub(_strip_long_code, text)
    # Strip JSON blobs
    text = _JSON_BLOB_RE.sub("", text)
    # Strip file path listings (3+ consecutive path-only lines)
    text = _FILE_LISTING_RE.sub("", text)
    # Strip remaining XML tags
    text = _XML_TAG_RE.sub("", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return ""

    # Take first substantive sentence
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for s in sentences:
        s = s.strip()
        if len(s) > 5:
            if len(s) <= max_length:
                return s
            return s[: max_length - 3] + "..."

    # No sentence boundary found — just truncate
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def extract_concepts(content: str) -> list[dict[str, str]]:
    """Extract typed concepts from content, deduplicated and normalized."""
    if not content:
        return []

    seen: set[tuple[str, str]] = set()
    concepts: list[dict[str, str]] = []

    def _add(name: str, ctype: str) -> None:
        key = (name.lower(), ctype)
        if key not in seen:
            seen.add(key)
            concepts.append({"name": name.lower(), "type": ctype})

    cl = content.lower()

    # Projects from paths
    for m in _PROJECT_PATH_RE.finditer(content):
        name = m.group(1).lower()
        canonical = _KNOWN_PROJECTS.get(name, name)
        _add(canonical, "project")

    # Projects from mentions
    for m in _PROJECT_MENTION_RE.finditer(content):
        name = m.group(1).lower()
        canonical = _KNOWN_PROJECTS.get(name, name)
        _add(canonical, "project")

    # Technologies
    for tech in _TECH_TERMS:
        if tech in cl:
            _add(tech, "technology")

    # Files
    for m in _FILE_RE.finditer(content):
        _add(m.group(1), "file")

    # Commands
    for m in _COMMAND_RE.finditer(cl):
        _add(m.group(1), "command")

    # Errors
    for m in _ERROR_RE.finditer(content):
        _add(m.group(1), "error")

    return concepts


def enrich_event(
    content: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Main entry point — enrich a single event with all classifiers."""
    topic = classify_topic(content, metadata)
    intent_label, intent_confidence = classify_intent(content)
    summary = extract_summary(content)
    concepts = extract_concepts(content)

    return {
        "topic": topic,
        "intent": intent_label,
        "intent_confidence": intent_confidence,
        "summary": summary,
        "concepts": concepts,
    }
