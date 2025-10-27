# Release Process

---

📚 **Navigation:** [🏠 Home](../../README.md) | [📖 Docs](../README.md) | [🤝 Contributing](../../CONTRIBUTING.md) | [📝 Changelog](../../CHANGELOG.md) | [🔒 Security](../security/SECRET_LEAK_RESPONSE.md)

---

This guide describes the release process for CrawlLama.

## Versioning

CrawlLama follows [Semantic Versioning](https://semver.org/):

```
MAJOR.MINOR.PATCH

Example: 1.3.0
```

- **MAJOR** (X.0.0): Breaking changes - incompatible API changes
- **MINOR** (x.X.0): New features - backward-compatible
- **PATCH** (x.x.X): Bug fixes - backward-compatible

## Release Types

### Patch Release (x.x.X)

For bug fixes and small improvements:

```bash
# Example: 1.3.0 → 1.3.1
- Bug fixes
- Performance improvements
- Documentation updates
- Dependency updates (minor)
```

### Minor Release (x.X.0)

For new features (backward-compatible):

```bash
# Example: 1.3.0 → 1.4.0
- New features
- New tools/plugins
- Extended APIs
- New configuration options
```

### Major Release (X.0.0)

For breaking changes:

```bash
# Example: 1.3.0 → 2.0.0
- API changes (breaking)
- Removed features
- Restructuring
- New architecture
```

## Release Workflow

### 1. Preparation

#### a) Determine version

Determine the new version number based on changes:

```bash
# Check current version
grep "Version" README.md

# Set new version
NEW_VERSION="1.4.0"
```

#### b) Create branch

```bash
git checkout -b release/v${NEW_VERSION}
```

### 2. Document Changes

#### a) Update CHANGELOG.md

```markdown
## [1.4.0] - 2025-01-25

### Added
- New feature X
- Tool Y integration

### Changed
- Improved feature Z

### Fixed
- Bug in module A
- Cache issue B

### Security
- Dependency update for package C
```

#### b) Update README.md

Update version and features:

```markdown
**Version 1.4** - Feature description

## 🔖 Versions

- **v1.4** (2025-01-25) - Feature description
  - Feature 1
  - Feature 2
```

### 3. Tests and Quality Checks

```bash
# Activate venv
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate      # Linux/macOS

# Run all tests
pytest tests/ -v --cov=core --cov=tools --cov=utils

# Security checks
pip-audit
safety check

# Code quality
flake8 core/ tools/ utils/ --max-line-length=100

# Type checking (optional)
mypy core/ tools/ utils/ --ignore-missing-imports
```

**Minimum requirements for release:**
- ✅ All tests green (≥95% passing)
- ✅ Coverage ≥45% (Preview) / ≥80% (Production release)
- ✅ No critical/high security vulnerabilities
- ✅ No secrets in code

### 4. Update Version Tags

Update version in all relevant files:

```bash
# Windows (PowerShell) - Manual edit
# Edit README.md, setup.py and other files manually

# Linux/macOS - sed
sed -i 's/Version [0-9]\+\.[0-9]\+/Version 1.4/' README.md
sed -i 's/version="[0-9]\+\.[0-9]\+\.[0-9]\+"/version="1.4.0"/' setup.py
```

**Note:** `sed -i` behaves differently on macOS (requires `sed -i ''`) vs GNU/Linux. On Windows use manual edits or PowerShell scripts.

### 5. Commit and Push

```bash
git add CHANGELOG.md README.md
git commit -m "chore(release): prepare v${NEW_VERSION}

- Update CHANGELOG.md
- Update README.md
- Update version numbers"

git push origin release/v${NEW_VERSION}
```

### 6. Create Pull Request

Create a PR from `release/v1.4.0` to `main`:

- **Title**: `Release v1.4.0`
- **Labels**: `release`
- **Description**: Copy relevant parts from CHANGELOG.md

**Review checklist:**
- [ ] CHANGELOG.md complete
- [ ] All tests green
- [ ] Documentation updated
- [ ] No breaking changes (or documented)

### 7. Merge and Tag

After approval:

```bash
# Merge PR to current release branch (v1.4)
git checkout v1.4
git pull origin v1.4

# Create tag
git tag -a v${NEW_VERSION} -m "Release v${NEW_VERSION}

- Feature 1
- Feature 2
- Bug fixes"

# Push tag
git push origin v${NEW_VERSION}
```

**Note:** This repo uses branch-based releases (v1.3, v1.4) instead of a central `main` branch. Adjust commands accordingly.

### 8. Create GitHub Release

1. Go to [Releases](https://github.com/arn-c0de/Crawllama/releases)
2. Click "Draft a new release"
3. Choose tag: `v1.4.0`
4. Release title: `CrawlLama v1.4.0 - Feature Name`
5. Description:

```markdown
# CrawlLama v1.4.0

**Release Date:** 2025-01-25

## 🎉 Highlights

- **Feature 1**: Description
- **Feature 2**: Description
- **Improvements**: Description

## 📋 Full Changelog

### Added
- Feature X
- Tool Y

### Changed
- Improvement Z

### Fixed
- Bug A
- Bug B

## 📦 Installation

```bash
git clone https://github.com/arn-c0de/Crawllama.git
cd Crawllama
git checkout v1.4.0
./setup.sh  # or setup.bat
```

## ⬆️ Upgrade from v1.3.x

```bash
cd Crawllama
git pull
git checkout v1.4.0
pip install -r requirements.txt
```

## 🔗 Links

- [Full Changelog](CHANGELOG.md)
- [Documentation](README.md)
- [Contributing Guide](CONTRIBUTING.md)

**Status: Production Ready ✅**
```

6. Click "Publish release"

### 9. Post-Release Tasks

#### a) Announce

- Update README badges (optional)

#### b) Monitor

Monitor for 24-48h after release:

```bash
# Check GitHub issues
# Collect feedback
# Hotfixes for critical bugs
```

#### c) Hotfix Process (if needed)

If critical bug after release:

```bash
# Hotfix branch
git checkout -b hotfix/v1.4.1 v1.4.0

# Implement fix
# Add tests

# Commit
git commit -m "fix(critical): description"

# Merge to main
git checkout main
git merge hotfix/v1.4.1

# Tag
git tag -a v1.4.1 -m "Hotfix v1.4.1"
git push origin v1.4.1

# GitHub release (as above)
```

## Release Checklist

Before each release:

### Code
- [ ] All tests green (`pytest tests/`)
- [ ] Coverage ≥80%
- [ ] No warnings in tests
- [ ] Code review completed

### Security
- [ ] `pip-audit` without critical/high
- [ ] `safety check` without vulnerabilities
- [ ] No secrets in code
- [ ] `.env.example` has only placeholders

### Documentation
- [ ] README.md updated
- [ ] CHANGELOG.md complete
- [ ] Breaking changes documented
- [ ] Migration guide (for major release)

### Quality
- [ ] flake8 without errors
- [ ] Type hints complete (optional)
- [ ] Docstrings updated
- [ ] Coverage ≥45% (Preview) / ≥80% (Production)

### Git
- [ ] Branch created from main
- [ ] Commit messages correct (Conventional Commits)
- [ ] PR review completed

### Release
- [ ] Version tag created
- [ ] GitHub release published
- [ ] Release notes complete

## Rollback Process

If major issues after release:

```bash
# Revert to previous version
git revert v1.4.0

# Or: Git reset (for severe problems)
git reset --hard v1.3.0
git push --force origin main

# Mark GitHub release as "yanked"
# Create new hotfix release
```

## Branching Strategy

```
main                 (production-ready)
  ├── develop        (development)
  │   ├── feature/*  (new features)
  │   ├── fix/*      (bug fixes)
  │   └── docs/*     (documentation)
  ├── release/*      (release preparation)
  └── hotfix/*       (critical fixes)
```

**Workflow:**
1. Feature branch from `develop`
2. PR to `develop`
3. Release branch from `develop`
4. PR to `main`
5. Tag on `main`

## Release Frequency

- **Patch**: As needed (hotfixes)
- **Minor**: Every 2-4 weeks
- **Major**: Every 3-6 months

## Automation (Future)

Planned CI/CD integration:

```yaml
# .github/workflows/release.yml
# Automatic:
# - Version bump
# - CHANGELOG update
# - Tests
# - Security checks
# - GitHub release
```

---

**Questions about the release process:** [GitHub Issues](https://github.com/arn-c0de/Crawllama/issues)
