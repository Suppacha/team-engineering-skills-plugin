from pathlib import Path
from pathlib import PurePosixPath
import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import unquote
from unittest import mock

MARKETPLACE_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = MARKETPLACE_ROOT / "plugins" / "team-engineering-skills"
LOCK_PATH = MARKETPLACE_ROOT / "config" / "skills-lock.json"
PACKAGED_SKILLS_ROOT = PLUGIN_ROOT / "skills"
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
MARKDOWN_REFERENCE_DEFINITION_RE = re.compile(
    r"^[ \t]{0,3}\[[^\]]+\]:[ \t]*(?:<([^>\n]+)>|(\S+))",
    re.MULTILINE,
)
MALFORMED_PERCENT_ESCAPE_RE = re.compile(r"%(?![0-9a-fA-F]{2})")
MAX_URL_DESTINATION_LENGTH = 8192
MAX_URL_DECODE_ITERATIONS = 64
TASK_ORIENTED_DESCRIPTION_RE = re.compile(
    r"\b(?:audit|build|create|debug|guide|hunt|identify|load|mentor|plan|prompt|"
    r"review|teach|test|use|when|write)\w*\b",
    re.IGNORECASE,
)
FORBIDDEN_PACKAGE_PARTS = {
    ".system",
    ".DS_Store",
    "__pycache__",
    "reverse-skill-router",
}

# These candidates have pinned redistribution evidence in the maintainer
# manifest. The five excluded candidates are deliberately not distributable.
APPROVED = {
    "acquire-codebase-knowledge",
    "create-agentsmd",
    "incident-postmortem",
    "load-testing",
    "mcp-builder",
    "mentoring-juniors",
    "property-based-testing",
    "selecting-quality-engineering-tools",
    "sharp-edges",
    "supabase",
    "supply-chain-risk-auditor",
    "variant-analysis",
}


def load_lock():
    return json.loads(LOCK_PATH.read_text())


def parse_skill_frontmatter(skill_md_path):
    """Read the scalar frontmatter fields the package contract relies on.

    The test suite deliberately has no PyYAML dependency so its standard-library
    verification gate can run with the system ``python3``. The release verifier
    separately runs the Codex validator, which performs full YAML parsing.
    """
    contents = skill_md_path.read_text(encoding="utf-8")
    assert contents.startswith("---\n"), f"missing frontmatter: {skill_md_path}"
    closing_marker = contents.find("\n---", 4)
    assert closing_marker != -1, f"unclosed frontmatter: {skill_md_path}"

    fields = {}
    for line in contents[4:closing_marker].splitlines():
        if not line or line.startswith((" ", "\t", "#")) or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            try:
                value = ast.literal_eval(value)
            except (SyntaxError, ValueError):
                value = value[1:-1]
        elif value.lower() == "false":
            value = False
        elif value.lower() == "true":
            value = True
        fields[key.strip()] = value
    return fields


def strip_yaml_inline_comment(value):
    """Remove an unquoted YAML comment without changing quoted scalar text."""
    quote = None
    escaped = False
    for index, character in enumerate(value):
        if escaped:
            escaped = False
        elif character == "\\" and quote == '"':
            escaped = True
        elif character in {"'", '"'}:
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
        elif character == "#" and quote is None:
            return value[:index].rstrip()
    return value.rstrip()


def agent_policy_disables_implicit_invocation(agent_manifest_path):
    """Return whether an OpenAI agent manifest explicitly opts out of invocation."""
    policy_indent = None
    for line in agent_manifest_path.read_text(encoding="utf-8").splitlines():
        uncommented = strip_yaml_inline_comment(line)
        if not uncommented.strip():
            continue
        indentation = len(uncommented) - len(uncommented.lstrip(" \t"))
        stripped = uncommented.strip()
        if policy_indent is None:
            if re.fullmatch(r"policy\s*:", stripped):
                policy_indent = indentation
            continue
        if indentation <= policy_indent:
            policy_indent = None
            if re.fullmatch(r"policy\s*:", stripped):
                policy_indent = indentation
            continue
        match = re.fullmatch(r"allow_implicit_invocation\s*:\s*(.*)", stripped)
        if match:
            return strip_yaml_inline_comment(match.group(1)).casefold() == "false"
    return False


def markdown_link_targets(contents):
    """Extract inline and reference-definition Markdown destinations."""
    targets = MARKDOWN_LINK_RE.findall(contents)
    for angle_bracket_target, bare_target in MARKDOWN_REFERENCE_DEFINITION_RE.findall(contents):
        targets.append(angle_bracket_target or bare_target)
    return targets


def normalize_markdown_destination(raw_target):
    """Decode a relative destination to convergence, rejecting unsafe inputs."""
    target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
    if len(target) > MAX_URL_DESTINATION_LENGTH:
        return None
    for _ in range(MAX_URL_DECODE_ITERATIONS):
        if MALFORMED_PERCENT_ESCAPE_RE.search(target):
            return None
        try:
            decoded_target = unquote(target, errors="strict")
        except UnicodeDecodeError:
            return None
        if len(decoded_target) > MAX_URL_DESTINATION_LENGTH:
            return None
        if decoded_target == target:
            return target
        target = decoded_target
    return None


def markdown_link_escapes_skill(skill_root, markdown_path, raw_target):
    """Reject relative links that escape the skill or reference missing files."""
    target = normalize_markdown_destination(raw_target)
    if target is None:
        return True
    if target.lower().startswith("file:") or (target.startswith("/") and not target.startswith("//")):
        return True
    if not target or target.startswith(("#", "//")) or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
        return False
    target_path = target.split("#", 1)[0].split("?", 1)[0].replace("\\", "/")
    if not target_path:
        return False
    resolved_target = (markdown_path.parent / target_path).resolve()
    return not resolved_target.is_relative_to(skill_root.resolve()) or not resolved_target.exists()


def package_path_is_forbidden(path):
    parts = PurePosixPath(path).parts
    return (
        any(part in FORBIDDEN_PACKAGE_PARTS for part in parts)
        or any(parts[index:index + 2] == ("plugins", "cache") for index in range(len(parts) - 1))
    )


def load_sync_module():
    script_path = MARKETPLACE_ROOT / "scripts" / "sync-skills.py"
    spec = importlib.util.spec_from_file_location("sync_skills_under_test", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def one_skill_lock(name="safe-skill"):
    return [{
        "name": name,
        "ownership": "Team-owned",
        "license": "Team-owned",
        "source": "test fixture",
        "revision": "test fixture",
    }]


def sync_fixture(module, source_root, plugin_root):
    module.plugin_root = plugin_root
    module.load_lock = lambda: one_skill_lock()
    with mock.patch.dict(os.environ, {"CODEX_SKILLS_SOURCE": str(source_root)}):
        module.sync()


def test_codex_plugin_scaffold_exists():
    manifest = json.loads(
        (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text()
    )
    assert manifest["name"] == "team-engineering-skills"
    assert (PLUGIN_ROOT / "skills").is_dir()


def test_codex_marketplace_points_to_plugin():
    catalog = json.loads(
        (MARKETPLACE_ROOT / ".agents" / "plugins" / "marketplace.json").read_text()
    )
    entry = next(p for p in catalog["plugins"] if p["name"] == "team-engineering-skills")
    assert entry["source"] == {"source": "local", "path": "./plugins/team-engineering-skills"}


def test_dual_manifests_share_identity_and_version():
    codex = json.loads((PLUGIN_ROOT / ".codex-plugin/plugin.json").read_text())
    claude = json.loads((PLUGIN_ROOT / ".claude-plugin/plugin.json").read_text())
    version = (PLUGIN_ROOT / "VERSION").read_text().strip()
    assert codex["name"] == claude["name"] == "team-engineering-skills"
    assert codex["version"] == claude["version"] == version == "2.0.0"


def test_claude_marketplace_uses_local_plugin_source():
    catalog = json.loads(
        (MARKETPLACE_ROOT / ".claude-plugin/marketplace.json").read_text()
    )
    entry = next(p for p in catalog["plugins"] if p["name"] == "team-engineering-skills")
    assert entry["source"] == "./plugins/team-engineering-skills"


def test_installation_documentation_covers_both_platforms_and_lifecycle():
    readme = (MARKETPLACE_ROOT / "README.md").read_text(encoding="utf-8")
    plugin_readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")
    documentation = f"{readme}\n{plugin_readme}"

    for required_text in (
        "Codex/ChatGPT",
        "Claude Code",
        "Install",
        "Update",
        "Uninstall",
        "Automatic invocation",
        "team-engineering-skills-marketplace",
        "team-engineering-skills",
    ):
        assert required_text in documentation, f"missing installation documentation: {required_text}"

    for required_text in (
        "/reload-plugins",
        "Start a **new session**",
        "team-engineering-skills@team-engineering-skills-marketplace",
        "Local ZIP/local-path testing",
        "Private-Git team distribution",
    ):
        assert required_text in documentation, f"missing platform installation detail: {required_text}"

    assert "rtk " not in documentation, "distributed documentation must not require rtk"


def test_smoke_tests_cover_the_required_team_workflows():
    smoke_tests = (MARKETPLACE_ROOT / "docs" / "SMOKE_TESTS.md").read_text(
        encoding="utf-8"
    ).casefold()

    for scenario in (
        "load",
        "browser e2e",
        "frontend design systems",
        "supply-chain audit",
        "supabase",
        "bug reproduction",
        "incident postmortem",
    ):
        assert scenario in smoke_tests, f"missing smoke-test scenario: {scenario}"


def test_skill_lock_matches_the_licensed_allowlist():
    lock = load_lock()
    skills = lock["skills"]
    names = [skill["name"] for skill in skills]

    assert set(names) == APPROVED
    assert len(names) == len(set(names)), "skills-lock.json must reject duplicate names"


def test_skill_lock_entries_have_license_provenance():
    for skill in load_lock()["skills"]:
        for field in ("ownership", "license", "source", "revision"):
            assert skill.get(field), f"{skill['name']} is missing {field}"


def test_packaged_skills_match_lock_and_contain_no_escaping_symlinks():
    expected_names = {skill["name"] for skill in load_lock()["skills"]}
    packaged_names = {path.name for path in PACKAGED_SKILLS_ROOT.iterdir() if path.is_dir()}
    assert packaged_names == expected_names

    root = PACKAGED_SKILLS_ROOT.resolve()
    for path in PACKAGED_SKILLS_ROOT.rglob("*"):
        if path.is_symlink():
            assert not os.path.isabs(os.readlink(path)), f"absolute symlink: {path}"
            assert path.resolve().is_relative_to(root), f"escaping symlink: {path}"


def test_skill_frontmatter_has_matching_name_and_task_oriented_description():
    for skill_md_path in sorted(PACKAGED_SKILLS_ROOT.glob("*/SKILL.md")):
        frontmatter = parse_skill_frontmatter(skill_md_path)
        name = frontmatter.get("name")
        description = frontmatter.get("description")

        assert isinstance(name, str) and name.strip(), f"missing name: {skill_md_path}"
        assert name == skill_md_path.parent.name, f"folder/name mismatch: {skill_md_path}"
        assert isinstance(description, str) and description.strip(), (
            f"missing description: {skill_md_path}"
        )
        assert TASK_ORIENTED_DESCRIPTION_RE.search(description), (
            f"description must describe a task: {skill_md_path}"
        )


def test_skill_agent_policies_allow_implicit_invocation():
    for agent_manifest_path in sorted(PACKAGED_SKILLS_ROOT.glob("*/agents/openai.yaml")):
        assert not agent_policy_disables_implicit_invocation(agent_manifest_path), (
            f"implicit invocation disabled: {agent_manifest_path}"
        )


def test_agent_policy_rejects_explicit_false_values_and_inline_comments():
    with tempfile.TemporaryDirectory() as temporary:
        agent_manifest_path = Path(temporary).resolve() / "openai.yaml"
        agent_manifest_path.write_text(
            "policy:\n  allow_implicit_invocation: false\n",
            encoding="utf-8",
        )
        assert agent_policy_disables_implicit_invocation(agent_manifest_path)

        agent_manifest_path.write_text(
            "policy:\n  allow_implicit_invocation: false # disabled\n",
            encoding="utf-8",
        )
        assert agent_policy_disables_implicit_invocation(agent_manifest_path)


def test_markdown_relative_links_stay_within_each_skill_directory():
    for skill_root in sorted(path for path in PACKAGED_SKILLS_ROOT.iterdir() if path.is_dir()):
        for markdown_path in skill_root.rglob("*.md"):
            contents = markdown_path.read_text(encoding="utf-8")
            escaping_links = [
                target for target in markdown_link_targets(contents)
                if markdown_link_escapes_skill(skill_root, markdown_path, target)
            ]
            assert not escaping_links, (
                f"relative links escape {skill_root.name}: {markdown_path}: {escaping_links}"
            )


def test_markdown_link_validation_rejects_reference_and_encoded_traversal():
    with tempfile.TemporaryDirectory() as temporary:
        skill_root = Path(temporary).resolve() / "skill"
        markdown_path = skill_root / "references" / "links.md"
        markdown_path.parent.mkdir(parents=True)

        markdown_path.write_text("[escape]: ../../outside.md\n", encoding="utf-8")
        reference_targets = markdown_link_targets(markdown_path.read_text(encoding="utf-8"))
        assert reference_targets == ["../../outside.md"]
        assert markdown_link_escapes_skill(skill_root, markdown_path, reference_targets[0])

        assert markdown_link_escapes_skill(
            skill_root,
            markdown_path,
            "%2e%2e/%2e%2e/outside.md",
        )

        assert markdown_link_escapes_skill(
            skill_root,
            markdown_path,
            "%252525252e%252525252e/%252525252e%252525252e/outside.md",
        )
        assert markdown_link_escapes_skill(skill_root, markdown_path, "%ZZ/outside.md")
        assert markdown_link_escapes_skill(skill_root, markdown_path, "%FF/outside.md")
        assert markdown_link_escapes_skill(skill_root, markdown_path, "a" * 8193)

        nested_percent_escape = "%2e%2e"
        for _ in range(MAX_URL_DECODE_ITERATIONS):
            nested_percent_escape = nested_percent_escape.replace("%", "%25")
        assert normalize_markdown_destination(nested_percent_escape) is None


def test_package_paths_exclude_internal_cache_and_platform_artifacts():
    forbidden_paths = [
        path.relative_to(PLUGIN_ROOT).as_posix()
        for path in PLUGIN_ROOT.rglob("*")
        if package_path_is_forbidden(path.relative_to(PLUGIN_ROOT).as_posix())
    ]
    assert not forbidden_paths, f"forbidden package paths: {forbidden_paths}"


def test_sync_rejects_an_allowed_destination_symlink_before_it_can_be_written():
    with tempfile.TemporaryDirectory() as temporary:
        temporary_root = Path(temporary).resolve()
        source_root = temporary_root / "source"
        (source_root / "safe-skill").mkdir(parents=True)
        (source_root / "safe-skill" / "SKILL.md").write_text("source payload")
        plugin_root = temporary_root / "plugin"
        destination_root = plugin_root / "skills"
        outside = temporary_root / "outside"
        outside.mkdir()
        destination_root.mkdir(parents=True)
        (destination_root / "safe-skill").symlink_to(outside, target_is_directory=True)

        module = load_sync_module()
        with unittest.TestCase().assertRaises(ValueError):
            sync_fixture(module, source_root, plugin_root)

        assert not (outside / "SKILL.md").exists()


def test_sync_rejects_a_symlinked_plugin_parent_before_it_can_be_written():
    with tempfile.TemporaryDirectory() as temporary:
        temporary_root = Path(temporary).resolve()
        source_root = temporary_root / "source"
        (source_root / "safe-skill").mkdir(parents=True)
        (source_root / "safe-skill" / "SKILL.md").write_text("source payload")
        outside = temporary_root / "outside"
        outside.mkdir()
        plugin_root = temporary_root / "plugin"
        plugin_root.symlink_to(outside, target_is_directory=True)

        module = load_sync_module()
        with unittest.TestCase().assertRaises(ValueError):
            sync_fixture(module, source_root, plugin_root)

        assert not (outside / "skills" / "safe-skill" / "SKILL.md").exists()


def test_sync_rejects_an_overlapping_source_and_destination_root():
    with tempfile.TemporaryDirectory() as temporary:
        plugin_root = Path(temporary).resolve() / "plugin"
        source_root = plugin_root / "skills"
        (source_root / "safe-skill").mkdir(parents=True)
        (source_root / "safe-skill" / "SKILL.md").write_text("source payload")

        module = load_sync_module()
        with unittest.TestCase().assertRaises(ValueError):
            sync_fixture(module, source_root, plugin_root)

        assert (source_root / "safe-skill" / "SKILL.md").read_text() == "source payload"


def test_sync_replaces_each_skill_with_a_clean_filtered_snapshot():
    with tempfile.TemporaryDirectory() as temporary:
        temporary_root = Path(temporary).resolve()
        source_root = temporary_root / "source"
        skill_root = source_root / "safe-skill"
        (skill_root / "__pycache__").mkdir(parents=True)
        (skill_root / "SKILL.md").write_text("first payload")
        (skill_root / "obsolete.md").write_text("obsolete source payload")
        (skill_root / "__pycache__" / "compiled.pyc").write_bytes(b"cache")
        (skill_root / ".DS_Store").write_bytes(b"cache")
        plugin_root = temporary_root / "plugin"
        module = load_sync_module()

        sync_fixture(module, source_root, plugin_root)
        packaged_skill = plugin_root / "skills" / "safe-skill"
        assert not (packaged_skill / "__pycache__").exists()
        assert not (packaged_skill / ".DS_Store").exists()
        assert (packaged_skill / "obsolete.md").exists()

        (skill_root / "obsolete.md").unlink()
        (skill_root / "SKILL.md").write_text("second payload")
        (packaged_skill / "revoked.md").write_text("revoked destination payload")
        sync_fixture(module, source_root, plugin_root)

        assert (packaged_skill / "SKILL.md").read_text() == "second payload"
        assert not (packaged_skill / "obsolete.md").exists()
        assert not (packaged_skill / "revoked.md").exists()


def test_notices_include_the_redistribution_license_materials():
    notices = (PLUGIN_ROOT / "THIRD_PARTY_NOTICES.md").read_text()
    assert "Copyright GitHub, Inc." in notices
    assert "Copyright (c) 2026 Supabase" in notices
    assert "Permission is hereby granted, free of charge" in notices
    assert "https://creativecommons.org/licenses/by-sa/4.0/" in notices
    assert "property-based-testing, sharp-edges, supply-chain-risk-auditor, and variant-analysis" in notices
    assert "mcp-builder/LICENSE.txt" in notices


def test_unverified_bug_reproduction_brief_is_excluded_by_the_license_gate():
    assert "bug-reproduction-brief" not in APPROVED
    assert "bug-reproduction-brief" not in {skill["name"] for skill in load_lock()["skills"]}
    assert not (PACKAGED_SKILLS_ROOT / "bug-reproduction-brief").exists()


def test_packaged_trail_of_bits_agent_manifests_meet_codex_requirements():
    for name in (
        "property-based-testing",
        "sharp-edges",
        "supply-chain-risk-auditor",
        "variant-analysis",
    ):
        agent_manifest = (PACKAGED_SKILLS_ROOT / name / "agents" / "openai.yaml").read_text()
        assert "display_name:" in agent_manifest
        assert "short_description:" in agent_manifest


def test_final_install_identity_matches_claude_catalog():
    catalog = json.loads((MARKETPLACE_ROOT / ".claude-plugin/marketplace.json").read_text())
    codex_catalog = json.loads((MARKETPLACE_ROOT / ".agents/plugins/marketplace.json").read_text())
    assert codex_catalog["name"] == catalog["name"]
    identity = f"{catalog['plugins'][0]['name']}@{catalog['name']}"
    for path in (MARKETPLACE_ROOT / "README.md", PLUGIN_ROOT / "README.md",
                 MARKETPLACE_ROOT / "docs/SMOKE_TESTS.md"):
        identities = re.findall(r"team-engineering-skills@[a-z-]+", path.read_text())
        assert identities and set(identities) == {identity}, (path, identities, identity)


def test_final_quality_skill_stands_alone_without_optional_skills():
    path = PACKAGED_SKILLS_ROOT / "selecting-quality-engineering-tools/SKILL.md"
    contents = path.read_text()
    for line in contents.splitlines():
        if "REQUIRED" in line:
            for name in re.findall(r"`([a-z-]+)`", line):
                assert (PACKAGED_SKILLS_ROOT / name / "SKILL.md").is_file(), name
    # Capability checks for the three standalone workflows, not exact prose.
    for concepts in (("locator", "assert", "trace"), ("scope", "passive", "active"),
                     ("accessibility", "component", "token")):
        assert all(word in contents.casefold() for word in concepts), concepts
    assert "optional" in contents.casefold()
    assert TASK_ORIENTED_DESCRIPTION_RE.search(parse_skill_frontmatter(path)["description"])


def test_final_sync_keeps_quality_skill_portable_without_editing_source():
    original = (
        "---\nname: selecting-quality-engineering-tools\n"
        "description: Use when selecting testing tools.\n---\n\n"
        "| Browser | Prefer the existing project framework. **REQUIRED SUB-SKILL:** Use `playwright` or the available Playwright testing skill. |\n"
        "| Security | Separate passive/baseline and active scans. **REQUIRED SUB-SKILL:** Use `api-security` or `pentest-tools`. |\n"
        "| Design | **REQUIRED SUB-SKILL:** Use `choose-frontend-design-system`. |\n"
        "\n## Selection workflow\n\nReuse existing tooling.\n"
    )
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        source = root / "source"
        name = "selecting-quality-engineering-tools"
        (source / name).mkdir(parents=True)
        source_file = source / name / "SKILL.md"
        source_file.write_text(original)
        module = load_sync_module()
        module.plugin_root = root / "plugin"
        module.load_lock = lambda: one_skill_lock(name)
        with mock.patch.dict(os.environ, {"CODEX_SKILLS_SOURCE": str(source)}):
            module.sync()
        packaged = (module.plugin_root / "skills" / name / "SKILL.md").read_text()
        assert "REQUIRED SUB-SKILL" not in packaged
        assert all(word in packaged for word in ("locator", "trace", "scope", "accessibility", "tokens"))
        assert source_file.read_text() == original


def test_final_sync_rejects_notice_symlink_before_any_mutation():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        source = root / "source"
        (source / "safe-skill").mkdir(parents=True)
        payload = source / "safe-skill/SKILL.md"
        payload.write_text("maintainer source")
        plugin = root / "plugin"
        (plugin / "skills/safe-skill").mkdir(parents=True)
        packaged = plugin / "skills/safe-skill/SKILL.md"
        packaged.write_text("previous package")
        (plugin / "THIRD_PARTY_NOTICES.md").symlink_to(payload)
        with unittest.TestCase().assertRaises(ValueError):
            sync_fixture(load_sync_module(), source, plugin)
        assert payload.read_text() == "maintainer source"
        assert packaged.read_text() == "previous package"


def test_final_sync_rejects_notice_overlap_and_symlinked_ancestor():
    for ancestor_link in (False, True):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "source"
            (source / "safe-skill").mkdir(parents=True)
            (source / "safe-skill/SKILL.md").write_text("source")
            if ancestor_link:
                (root / "alias").symlink_to(root, target_is_directory=True)
                plugin = root / "alias/plugin"
            else:
                plugin = source
            with unittest.TestCase().assertRaises(ValueError):
                sync_fixture(load_sync_module(), source, plugin)
            assert not (source / "THIRD_PARTY_NOTICES.md").exists()


def test_final_license_gate_rejects_unverified_and_incomplete_evidence():
    valid = next(s for s in load_lock()["skills"] if s["name"] == "acquire-codebase-knowledge")
    changes = [{"ownership": "Unverified"}, {"license": "UNKNOWN"}, {"license": "TBD"},
               {"ownership": ""}, {"source": "UNKNOWN"}, {"revision": "main"},
               {"attribution": ""}, {"notice": None}]
    for change in changes:
        with tempfile.TemporaryDirectory() as temporary:
            module = load_sync_module()
            module.lock_path = Path(temporary).resolve() / "lock.json"
            module.lock_path.write_text(json.dumps({"skills": [{**valid, **change}]}))
            with unittest.TestCase().assertRaises(ValueError, msg=str(change)):
                module.load_lock()


def test_final_notices_are_grouped_from_lock_evidence():
    module = load_sync_module()
    skill = dict(next(s for s in load_lock()["skills"] if s["name"] == "acquire-codebase-knowledge"))
    skill["name"] = "renamed-example"
    with tempfile.TemporaryDirectory() as temporary:
        module.plugin_root = Path(temporary).resolve()
        module.write_notices([skill])
        notices = (module.plugin_root / "THIRD_PARTY_NOTICES.md").read_text()
        assert "Applies to: renamed-example." in notices
        for unrelated in ("acquire-codebase-knowledge", "supabase", "mcp-builder", "variant-analysis"):
            assert unrelated not in notices


def test_final_packaged_notices_cover_exactly_the_validated_ledger():
    module = load_sync_module()
    skills = module.load_lock()
    assert (PLUGIN_ROOT / "THIRD_PARTY_NOTICES.md").read_text() == module.render_notices(skills)
    for skill in skills:
        license_file = skill.get("notice", {}).get("license_file")
        if license_file:
            assert (PACKAGED_SKILLS_ROOT / skill["name"] / license_file).is_file()


def test_final_sync_rejects_missing_license_material_before_mutation():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        source = root / "source"
        (source / "mcp-builder").mkdir(parents=True)
        (source / "mcp-builder/SKILL.md").write_text("source")
        plugin = root / "plugin"
        module = load_sync_module()
        module.plugin_root = plugin
        entry = next(s for s in load_lock()["skills"] if s["name"] == "mcp-builder")
        module.load_lock = lambda: [entry]
        with mock.patch.dict(os.environ, {"CODEX_SKILLS_SOURCE": str(source)}):
            with unittest.TestCase().assertRaises(ValueError):
                module.sync()
        assert not plugin.exists()


def test_final_markdown_rejects_missing_local_targets_but_allows_fragments_and_urls():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        markdown = root / "SKILL.md"
        markdown.write_text("# Existing")
        assert markdown_link_escapes_skill(root, markdown, "missing.md")
        assert markdown_link_escapes_skill(root, markdown, "missing.md#anchor")
        assert markdown_link_escapes_skill(root, markdown, "/missing.md")
        assert markdown_link_escapes_skill(root, markdown, "file:///missing.md")
        for target in ("#existing", "SKILL.md#existing", "https://example.com/missing.md", "mailto:a@example.com"):
            assert not markdown_link_escapes_skill(root, markdown, target), target


def test_final_optional_validator_skip_and_rejection():
    for mode in ("missing-validator", "missing-yaml", "reject"):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "dirname").symlink_to("/usr/bin/dirname")
            validator = root / "validator.py"
            validator.write_text("raise SystemExit(7)\n")
            python = root / "python"
            python.write_text(
                "#!/bin/sh\nif [ \"$1\" = -c ]; then exit "
                + ("1" if mode == "missing-yaml" else "0")
                + f"; fi\nexec {sys.executable} \"$@\"\n"
            )
            python.chmod(0o755)
            (root / "python3").symlink_to(python)
            env = {**os.environ, "PATH": str(root), "PYTHON_BIN": "/usr/bin/true",
                   "CODEX_VALIDATOR_PYTHON": str(python),
                   "CODEX_PLUGIN_VALIDATOR": str(root / "absent" if mode == "missing-validator" else validator)}
            result = subprocess.run(["/bin/bash", str(MARKETPLACE_ROOT / "scripts/verify-package.sh")],
                                    env=env, capture_output=True, text=True)
            output = result.stdout + result.stderr
            if mode == "reject":
                assert result.returncode != 0, output
                assert "Package verification PASS" not in output
            else:
                assert result.returncode == 0, (mode, output)
                assert "SKIP" in output and "JSON manifest parsing" in output, output


def load_tests(loader, tests, pattern):
    """Expose the required function-based checks to unittest discovery."""
    suite = unittest.TestSuite()
    for name, function in sorted(globals().items()):
        if name.startswith("test_final_"):
            suite.addTest(unittest.FunctionTestCase(function))
    suite.addTest(unittest.FunctionTestCase(test_codex_plugin_scaffold_exists))
    suite.addTest(unittest.FunctionTestCase(test_codex_marketplace_points_to_plugin))
    suite.addTest(unittest.FunctionTestCase(test_dual_manifests_share_identity_and_version))
    suite.addTest(unittest.FunctionTestCase(test_claude_marketplace_uses_local_plugin_source))
    suite.addTest(unittest.FunctionTestCase(test_installation_documentation_covers_both_platforms_and_lifecycle))
    suite.addTest(unittest.FunctionTestCase(test_smoke_tests_cover_the_required_team_workflows))
    suite.addTest(unittest.FunctionTestCase(test_skill_lock_matches_the_licensed_allowlist))
    suite.addTest(unittest.FunctionTestCase(test_skill_lock_entries_have_license_provenance))
    suite.addTest(unittest.FunctionTestCase(test_packaged_skills_match_lock_and_contain_no_escaping_symlinks))
    suite.addTest(unittest.FunctionTestCase(test_skill_frontmatter_has_matching_name_and_task_oriented_description))
    suite.addTest(unittest.FunctionTestCase(test_skill_agent_policies_allow_implicit_invocation))
    suite.addTest(unittest.FunctionTestCase(test_agent_policy_rejects_explicit_false_values_and_inline_comments))
    suite.addTest(unittest.FunctionTestCase(test_markdown_relative_links_stay_within_each_skill_directory))
    suite.addTest(unittest.FunctionTestCase(test_markdown_link_validation_rejects_reference_and_encoded_traversal))
    suite.addTest(unittest.FunctionTestCase(test_package_paths_exclude_internal_cache_and_platform_artifacts))
    suite.addTest(unittest.FunctionTestCase(test_sync_rejects_an_allowed_destination_symlink_before_it_can_be_written))
    suite.addTest(unittest.FunctionTestCase(test_sync_rejects_a_symlinked_plugin_parent_before_it_can_be_written))
    suite.addTest(unittest.FunctionTestCase(test_sync_rejects_an_overlapping_source_and_destination_root))
    suite.addTest(unittest.FunctionTestCase(test_sync_replaces_each_skill_with_a_clean_filtered_snapshot))
    suite.addTest(unittest.FunctionTestCase(test_notices_include_the_redistribution_license_materials))
    suite.addTest(unittest.FunctionTestCase(test_unverified_bug_reproduction_brief_is_excluded_by_the_license_gate))
    suite.addTest(unittest.FunctionTestCase(test_packaged_trail_of_bits_agent_manifests_meet_codex_requirements))
    return suite
