#!/usr/bin/env python3
"""
Extract all packages from requirements.txt (including commented-out ones)
and write them to packages_to_check.txt for easy update review.
"""

import re
from pathlib import Path

REQUIREMENTS_FILE = Path("requirements.txt")
OUTPUT_FILE = Path("packages_to_check.txt")

# Standard pip specifier: name followed by operator and version
RE_SPECIFIER = re.compile(r"^([A-Za-z0-9_\-\.]+)((?:>=|<=|==|!=|~=|>|<)[^\s#]+)")

# Plain version number (e.g. "dataclasses-json 0.6.7 declares ...")
RE_PLAIN_VERSION = re.compile(r"^([A-Za-z0-9_\-\.]+)\s+(\d[\d\.]+)")

# TODO/FIXME: package-name (no version available yet, but tracked)
RE_TODO = re.compile(r"^(?:TODO|FIXME)[:\s]+([A-Za-z0-9_\-\.]+)", re.IGNORECASE)

# Words that are never package names
SKIP_WORDS = {
    "see", "also", "fix", "if", "only", "requires", "installing",
    "workaround", "affected", "this", "monitor", "ensure", "avoid",
    "no", "patch", "available", "yet", "implement", "application",
    "level", "or", "when", "using", "with", "for", "and", "but",
    "works", "correctly", "security", "takes", "priority", "over",
    "dep", "resolver", "warning", "imports", "may", "pull", "which",
    "can", "conflict", "other", "packages", "direct", "access",
    "account", "email", "password", "environment", "variables",
    "docs", "osint", "setup", "implications",
}


def parse_line(content: str) -> str | None:
    """Try to extract a package entry from a stripped content string."""
    # 1. Standard pip specifier
    m = RE_SPECIFIER.match(content)
    if m:
        name = m.group(1)
        if name.lower() not in SKIP_WORDS:
            return f"{name}{m.group(2)}"

    # 2. TODO/NOTE: package-name (no version)
    m = RE_TODO.match(content)
    if m:
        name = m.group(1)
        if name.lower() not in SKIP_WORDS:
            return name

    # 3. package-name plain-version (e.g. "dataclasses-json 0.6.7 ...")
    m = RE_PLAIN_VERSION.match(content)
    if m:
        name = m.group(1)
        if name.lower() not in SKIP_WORDS and "-" in name or "_" in name or len(name) > 4:
            return f"{name}=={m.group(2)}"

    return None


def extract_packages(req_file: Path) -> tuple[list, list]:
    active = []
    commented = []

    for raw_line in req_file.read_text().splitlines():
        line = raw_line.strip()

        if not line or line.startswith("##"):
            continue

        is_commented = line.startswith("#")
        content = line.lstrip("#").strip()

        entry = parse_line(content)
        if entry:
            (commented if is_commented else active).append(entry)

    return active, commented


def main():
    if not REQUIREMENTS_FILE.exists():
        print(f"Error: {REQUIREMENTS_FILE} not found.")
        return

    active, commented = extract_packages(REQUIREMENTS_FILE)

    all_packages = active + commented
    OUTPUT_FILE.write_text("\n".join(all_packages) + "\n")
    print(f"Written {len(all_packages)} packages to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
