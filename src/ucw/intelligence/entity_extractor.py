"""
Entity Extractor — Lightweight keyword-based entity extraction

NO external NLP libraries. Pure Python regex + keyword matching.
Extracts: person, organization, technology, concept, project, tool, platform
"""

import re
from typing import Dict, List, Optional

# Known technology terms (lowercase for matching)
TECHNOLOGY_TERMS = {
    "python", "javascript", "typescript", "react", "vue", "angular", "svelte",
    "docker", "kubernetes", "k8s", "terraform", "ansible", "nginx", "redis",
    "postgres", "postgresql", "mysql", "sqlite", "mongodb", "dynamodb",
    "graphql", "rest", "grpc", "websocket", "http", "https",
    "node", "nodejs", "deno", "bun", "rust", "go", "golang", "java", "kotlin",
    "swift", "c++", "cpp", "c#", "csharp", "ruby", "php", "scala", "elixir",
    "html", "css", "sass", "tailwind", "webpack", "vite", "rollup", "esbuild",
    "git", "github", "gitlab", "bitbucket", "cicd", "jenkins", "circleci",
    "aws", "azure", "gcp", "vercel", "netlify", "heroku", "railway", "fly",
    "linux", "macos", "windows", "wasm", "webassembly",
    "langchain", "llamaindex", "openai", "anthropic", "huggingface",
    "pytorch", "tensorflow", "numpy", "pandas", "scikit-learn",
    "fastapi", "flask", "django", "express", "nextjs", "next.js", "nuxt",
    "supabase", "firebase", "prisma", "drizzle", "sqlalchemy",
    "mcp", "json-rpc", "sse", "oauth", "jwt", "api",
}

# AI tool names (lowercase)
TOOL_TERMS = {
    "claude", "chatgpt", "gpt-4", "gpt-4o", "gpt-3.5", "gemini", "copilot",
    "cursor", "windsurf", "cody", "tabnine", "codium", "aider",
    "midjourney", "dall-e", "dalle", "stable diffusion", "flux",
    "perplexity", "phind", "you.com", "bard",
    "notion", "obsidian", "logseq", "roam",
    "vercel ai", "replicate", "together ai", "groq", "ollama",
    "whisper", "eleven labs", "descript",
}

# Platform names (lowercase)
PLATFORM_TERMS = {
    "github", "gitlab", "bitbucket", "stackoverflow", "stack overflow",
    "twitter", "x.com", "linkedin", "discord", "slack", "reddit",
    "youtube", "twitch", "medium", "dev.to", "hashnode",
    "figma", "notion", "linear", "jira", "asana", "trello",
    "vercel", "netlify", "heroku", "railway", "fly.io",
    "aws", "azure", "gcp", "google cloud", "cloudflare",
    "npm", "pypi", "crates.io", "docker hub",
    "hacker news", "producthunt", "product hunt",
}

# Organization indicators (lowercase)
ORGANIZATION_INDICATORS = {
    "openai", "anthropic", "google", "microsoft", "meta", "apple", "amazon",
    "nvidia", "intel", "amd", "arm", "qualcomm",
    "stripe", "shopify", "salesforce", "oracle", "ibm", "sap",
    "netflix", "spotify", "uber", "airbnb", "dropbox",
    "bytedance", "tencent", "alibaba", "baidu",
    "y combinator", "andreessen horowitz", "a16z", "sequoia",
    "mit", "stanford", "berkeley", "harvard", "oxford", "cambridge",
}

# Person name pattern: two or more capitalized words in sequence
# e.g. "John Smith", "Elon Musk", "Dico Angelo"
_PERSON_PATTERN = re.compile(
    r"\b([A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20})+)\b"
)

# Filter out common false positives for person names
_PERSON_EXCLUDE = {
    "the", "this", "that", "with", "from", "about", "into", "over",
    "after", "before", "between", "through", "during", "without",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    "new york", "san francisco", "los angeles", "united states",
    "north america", "south america", "east coast", "west coast",
    "machine learning", "deep learning", "natural language",
    "open source", "pull request", "merge request",
}


def extract_entities(
    text: str,
    topic: str = "",
    concepts: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Extract entities from text using regex patterns and keyword matching.

    Returns list of {"name": str, "type": str, "confidence": float}
    Deduplicates by lowercased name.
    """
    if not text:
        return []

    seen: Dict[str, Dict] = {}  # lowercase name -> entity dict
    text_lower = text.lower()
    combined = f"{text} {topic}"

    # --- Technology terms ---
    for term in TECHNOLOGY_TERMS:
        if term in text_lower:
            _add_entity(seen, term.title() if len(term) <= 3 else term, "technology", 0.9)

    # --- Tool terms ---
    for term in TOOL_TERMS:
        if term in text_lower:
            _add_entity(seen, term, "tool", 0.9)

    # --- Platform terms ---
    for term in PLATFORM_TERMS:
        if term in text_lower:
            _add_entity(seen, term, "platform", 0.9)

    # --- Organization terms ---
    for term in ORGANIZATION_INDICATORS:
        if term in text_lower:
            _add_entity(seen, term, "organization", 0.9)

    # --- Person names (capitalized word pairs) ---
    for match in _PERSON_PATTERN.finditer(combined):
        name = match.group(1)
        if name.lower() not in _PERSON_EXCLUDE:
            # Check it's not already captured as org/tech/tool/platform
            if name.lower() not in seen:
                _add_entity(seen, name, "person", 0.6)

    # --- Concepts from the concepts list ---
    if concepts:
        for concept in concepts:
            if concept and concept.strip():
                key = concept.strip().lower()
                if key not in seen:
                    _add_entity(seen, concept.strip(), "concept", 0.7)

    # --- Project names: look for words after "project", "repo", "app" ---
    project_pattern = re.compile(
        r"\b(?:project|repo|repository|app|application|package|library|codebase)\s+"
        r"([A-Za-z][A-Za-z0-9_-]{1,40})\b",
        re.IGNORECASE,
    )
    for match in project_pattern.finditer(combined):
        name = match.group(1)
        stop_words = {
            "the", "a", "an", "is", "was", "and", "or", "for",
        }
        if name.lower() not in seen and name.lower() not in stop_words:
            _add_entity(seen, name, "project", 0.6)

    return list(seen.values())


def _add_entity(seen: Dict[str, Dict], name: str, entity_type: str, confidence: float):
    """Add entity to seen dict, keeping higher confidence on collision."""
    key = name.lower()
    if key in seen:
        if confidence > seen[key]["confidence"]:
            seen[key]["confidence"] = confidence
    else:
        seen[key] = {
            "name": name,
            "type": entity_type,
            "confidence": confidence,
        }
