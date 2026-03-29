"""Tests for UCW enrichment pipeline."""

from ucw.enrichment import (
    classify_intent,
    classify_topic,
    enrich_event,
    extract_concepts,
    extract_summary,
)

# ===================================================================
# classify_topic
# ===================================================================


class TestClassifyTopic:
    """Topic classification tests."""

    def test_project_from_products_path(self):
        assert classify_topic("editing /projects/products/ucw/src/main.py") == "ucw"

    def test_project_from_apps_path(self):
        content = "look at /projects/apps/CareerCoachAntigravity/pages/index.tsx"
        assert classify_topic(content) == "careercoach"

    def test_project_from_core_path(self):
        assert classify_topic("in /projects/core/meta-vengine/router.py") == "meta-vengine"

    def test_project_from_metadata_cwd(self):
        meta = {"cwd": "/Users/dico/projects/products/friendlyface"}
        assert classify_topic("some generic content", meta) == "friendlyface"

    def test_project_from_metadata_project_dir(self):
        meta = {"project_dir": "/home/user/projects/apps/os-app"}
        assert classify_topic("generic", meta) == "os-app"

    def test_explicit_mention_friendlyface(self):
        assert classify_topic("Working on FriendlyFace auth flow") == "friendlyface"

    def test_explicit_mention_openviking(self):
        assert classify_topic("Integrate with OpenViking context DB") == "openviking"

    def test_domain_classification_auth(self):
        assert classify_topic("fix the JWT token refresh and oauth flow") == "authentication"

    def test_domain_classification_database(self):
        assert classify_topic("run the sqlite migration and update schema") == "database"

    def test_domain_classification_frontend(self):
        assert classify_topic("update the react component with tailwind styles") == "frontend"

    def test_domain_classification_testing(self):
        assert classify_topic("add pytest fixtures and increase coverage") == "testing"

    def test_fallback_general(self):
        assert classify_topic("hello world") == "general"

    def test_empty_content(self):
        assert classify_topic("") == "general"

    def test_none_metadata(self):
        assert classify_topic("generic stuff", None) == "general"

    def test_path_takes_priority_over_domain(self):
        content = "deploy /projects/products/ucw/server.py to vercel"
        assert classify_topic(content) == "ucw"


# ===================================================================
# classify_intent
# ===================================================================


class TestClassifyIntent:
    """Intent classification tests."""

    def test_build_intent(self):
        label, conf = classify_intent("create a new file for the enrichment pipeline")
        assert label == "build"
        assert conf > 0.0

    def test_debug_intent(self):
        label, conf = classify_intent("fix this bug, the test is failing with an error")
        assert label == "debug"
        assert conf > 0.0

    def test_debug_traceback(self):
        label, conf = classify_intent("Traceback (most recent call last):\n  File x.py")
        assert label == "debug"

    def test_refactor_intent(self):
        label, _ = classify_intent("refactor and clean up the module, rename the class")
        assert label == "refactor"

    def test_research_intent(self):
        label, _ = classify_intent("how does the MCP protocol work? explain the transport")
        assert label == "research"

    def test_review_intent(self):
        label, _ = classify_intent("review the PR and audit the changes")
        assert label == "review"

    def test_deploy_intent(self):
        label, _ = classify_intent("deploy and publish the release to production")
        assert label == "deploy"

    def test_configure_intent(self):
        label, _ = classify_intent("setup the env and config settings for production")
        assert label == "configure"

    def test_plan_intent(self):
        label, _ = classify_intent("plan the roadmap and architect the strategy")
        assert label == "plan"

    def test_discuss_fallback(self):
        label, conf = classify_intent("hello there")
        assert label == "discuss"
        assert conf <= 0.2

    def test_empty_content(self):
        label, conf = classify_intent("")
        assert label == "discuss"
        assert conf == 0.0

    def test_confidence_bounded(self):
        _, conf = classify_intent("create add implement write new file build make")
        assert 0.0 <= conf <= 1.0


# ===================================================================
# extract_summary
# ===================================================================


class TestExtractSummary:
    """Summary extraction tests."""

    def test_simple_sentence(self):
        assert extract_summary("Fix the login bug.") == "Fix the login bug."

    def test_strips_code_blocks(self):
        content = (
            "Here is the fix.\n```python\ndef foo():\n"
            "    pass\n    pass\n    pass\n    pass\n```\nDone."
        )
        result = extract_summary(content)
        assert "def foo" not in result
        assert "Here is the fix." in result

    def test_strips_xml_tags(self):
        result = extract_summary("<bold>Important</bold> update here.")
        assert "<bold>" not in result
        assert "Important" in result

    def test_strips_json_blobs(self):
        blob = '{"key": "' + "x" * 120 + '"}'
        result = extract_summary(f"Starting work. {blob} Ending.")
        assert "Starting work." in result

    def test_truncation(self):
        long_text = "A" * 300
        result = extract_summary(long_text, max_length=50)
        assert len(result) <= 50
        assert result.endswith("...")

    def test_empty_content(self):
        assert extract_summary("") == ""

    def test_pure_code_block(self):
        content = "```python\ndef foo():\n    x = 1\n    y = 2\n    z = 3\n    return x\n```"
        assert extract_summary(content) == ""

    def test_max_length_respected(self):
        result = extract_summary("Short sentence here.", max_length=200)
        assert len(result) <= 200


# ===================================================================
# extract_concepts
# ===================================================================


class TestExtractConcepts:
    """Concept extraction tests."""

    def test_project_from_path(self):
        concepts = extract_concepts("editing /projects/products/ucw/main.py")
        names = [c["name"] for c in concepts if c["type"] == "project"]
        assert "ucw" in names

    def test_technology_detection(self):
        concepts = extract_concepts("using react and tailwind with vite")
        techs = [c["name"] for c in concepts if c["type"] == "technology"]
        assert "react" in techs
        assert "tailwind" in techs

    def test_file_detection(self):
        concepts = extract_concepts("edit server.py and index.tsx")
        files = [c["name"] for c in concepts if c["type"] == "file"]
        assert "server.py" in files
        assert "index.tsx" in files

    def test_command_detection(self):
        concepts = extract_concepts("run git status and npm install")
        cmds = [c["name"] for c in concepts if c["type"] == "command"]
        assert "git" in cmds
        assert "npm" in cmds

    def test_error_detection(self):
        concepts = extract_concepts("got a TypeError and ImportError")
        errors = [c["name"] for c in concepts if c["type"] == "error"]
        assert "typeerror" in errors
        assert "importerror" in errors

    def test_deduplication(self):
        concepts = extract_concepts("ucw UCW /projects/products/ucw/x.py ucw")
        project_concepts = [c for c in concepts if c["type"] == "project" and c["name"] == "ucw"]
        assert len(project_concepts) == 1

    def test_empty_content(self):
        assert extract_concepts("") == []


# ===================================================================
# enrich_event
# ===================================================================


class TestEnrichEvent:
    """Integration tests for the main entry point."""

    def test_returns_all_keys(self):
        result = enrich_event("create a new react component")
        assert "topic" in result
        assert "intent" in result
        assert "intent_confidence" in result
        assert "summary" in result
        assert "concepts" in result

    def test_full_enrichment(self):
        content = "Fix the bug in /projects/products/friendlyface/auth.py — TypeError on login"
        result = enrich_event(content)
        assert result["topic"] == "friendlyface"
        assert result["intent"] == "debug"
        assert result["intent_confidence"] > 0.0
        assert "Fix the bug" in result["summary"]
        errors = [c for c in result["concepts"] if c["type"] == "error"]
        assert any(c["name"] == "typeerror" for c in errors)

    def test_metadata_passthrough(self):
        result = enrich_event(
            "working on stuff",
            metadata={"cwd": "/Users/x/projects/products/ucw"},
        )
        assert result["topic"] == "ucw"

    def test_very_short_content(self):
        result = enrich_event("hi")
        assert result["topic"] == "general"
        assert result["intent"] == "discuss"
