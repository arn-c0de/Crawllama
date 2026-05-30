#!/usr/bin/env python3
"""
Extract all declared packages from pyproject.toml (core dependencies, every
optional-dependency extra, and the uv security override pins) and write them to
packages_to_check.txt for easy update review.

This replaced the old requirements.txt-based extractor when the project moved to
uv: pyproject.toml + uv.lock are now the single source of truth.
"""

import re
import tomllib
from pathlib import Path

PYPROJECT_FILE = Path("pyproject.toml")
OUTPUT_FILE = Path("packages_to_check.txt")

# PEP 508 requirement: name followed by optional extras/version specifier.
RE_REQUIREMENT = re.compile(r"^([A-Za-z0-9_][A-Za-z0-9_.\-]*)\s*(\[[^\]]*\])?\s*(.*)$")

# Self-referential extras such as "crawllama[api,osint,...]" are aggregates, not
# real packages — skip them.
PROJECT_NAME = "crawllama"


def normalize(req: str) -> str | None:
    """Return the requirement string without its inline marker/comment, or None."""
    req = req.split(";", 1)[0].strip()  # drop environment markers
    if not req:
        return None
    m = RE_REQUIREMENT.match(req)
    if not m:
        return None
    name = m.group(1)
    if name.lower() == PROJECT_NAME:
        return None
    return req


def extract_packages(pyproject: Path) -> tuple[list[str], list[str]]:
    """Return (core, optional) requirement lists parsed from pyproject.toml."""
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data.get("project", {})

    core: list[str] = []
    for dep in project.get("dependencies", []):
        entry = normalize(dep)
        if entry:
            core.append(entry)

    optional: list[str] = []
    seen = set(core)
    for deps in project.get("optional-dependencies", {}).values():
        for dep in deps:
            entry = normalize(dep)
            if entry and entry not in seen:
                seen.add(entry)
                optional.append(entry)

    # uv security override pins (transitive packages force-pinned for CVE fixes).
    for dep in data.get("tool", {}).get("uv", {}).get("override-dependencies", []):
        entry = normalize(dep)
        if entry and entry not in seen:
            seen.add(entry)
            optional.append(entry)

    return core, optional


def main():
    if not PYPROJECT_FILE.exists():
        print(f"Error: {PYPROJECT_FILE} not found.")
        return

    core, optional = extract_packages(PYPROJECT_FILE)

    all_packages = core + optional
    OUTPUT_FILE.write_text("\n".join(all_packages) + "\n")
    print(f"Written {len(all_packages)} packages to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
