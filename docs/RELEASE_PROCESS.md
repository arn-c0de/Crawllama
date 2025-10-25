# Release-Prozess

---

📚 **Navigation:** [🏠 Home](../README.md) | [📖 Docs](README.md) | [🤝 Contributing](../CONTRIBUTING.md) | [📝 Changelog](../CHANGELOG.md) | [🔒 Security](SECRET_LEAK_RESPONSE.md)

---

Dieser Leitfaden beschreibt den Release-Prozess für CrawlLama.

## Versionierung

CrawlLama folgt [Semantic Versioning](https://semver.org/lang/de/):

```
MAJOR.MINOR.PATCH

Beispiel: 1.3.0
```

- **MAJOR** (X.0.0): Breaking Changes - Inkompatible API-Änderungen
- **MINOR** (x.X.0): Neue Features - Backward-compatible
- **PATCH** (x.x.X): Bug-Fixes - Backward-compatible

## Release-Typen

### Patch Release (x.x.X)

Für Bug-Fixes und kleine Verbesserungen:

```bash
# Beispiel: 1.3.0 → 1.3.1
- Bug-Fixes
- Performance-Verbesserungen
- Dokumentations-Updates
- Dependency-Updates (minor)
```

### Minor Release (x.X.0)

Für neue Features (backward-compatible):

```bash
# Beispiel: 1.3.0 → 1.4.0
- Neue Features
- Neue Tools/Plugins
- Erweiterte APIs
- Neue Konfigurationsoptionen
```

### Major Release (X.0.0)

Für Breaking Changes:

```bash
# Beispiel: 1.3.0 → 2.0.0
- API-Änderungen (breaking)
- Entfernte Features
- Umstrukturierung
- Neue Architektur
```

## Release-Workflow

### 1. Vorbereitung

#### a) Version festlegen

Bestimme die neue Versionsnummer basierend auf den Änderungen:

```bash
# Aktuelle Version prüfen
grep "Version" README.md

# Neue Version festlegen
NEW_VERSION="1.4.0"
```

#### b) Branch erstellen

```bash
git checkout -b release/v${NEW_VERSION}
```

### 2. Änderungen dokumentieren

#### a) CHANGELOG.md aktualisieren

```markdown
## [1.4.0] - 2025-01-25

### Added
- Neues Feature X
- Tool Y Integration

### Changed
- Verbessertes Feature Z

### Fixed
- Bug in Modul A
- Cache-Problem B

### Security
- Dependency-Update für Package C
```

#### b) README.md aktualisieren

Update Version und Features:

```markdown
**Version 1.4** - Feature Description

## 🔖 Versionen

- **v1.4** (2025-01-25) - Feature Description
  - Feature 1
  - Feature 2
```

### 3. Tests und Quality Checks

```bash
# Aktiviere venv
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate      # Linux/macOS

# Alle Tests ausführen
pytest tests/ -v --cov=core --cov=tools --cov=utils

# Security-Checks
pip-audit
safety check

# Code-Quality
flake8 core/ tools/ utils/ --max-line-length=100

# Type-Checking (optional)
mypy core/ tools/ utils/ --ignore-missing-imports
```

**Mindestanforderungen für Release:**
- ✅ Alle Tests grün (≥95% passing)
- ✅ Coverage ≥45% (Preview) / ≥80% (Production Release)
- ✅ Keine Critical/High Security Vulnerabilities
- ✅ Keine Secrets im Code

### 4. Version-Tags aktualisieren

Update Version in allen relevanten Dateien:

```bash
# Windows (PowerShell) - Manual Edit
# Edit README.md, setup.py und andere Dateien manuell

# Linux/macOS - sed
sed -i 's/Version [0-9]\+\.[0-9]\+/Version 1.4/' README.md
sed -i 's/version="[0-9]\+\.[0-9]\+\.[0-9]\+"/version="1.4.0"/' setup.py
```

**Hinweis:** `sed -i` verhält sich unterschiedlich auf macOS (benötigt `sed -i ''`) vs GNU/Linux. Auf Windows verwende manuelle Edits oder PowerShell-Scripts.

### 5. Commit und Push

```bash
git add CHANGELOG.md README.md
git commit -m "chore(release): prepare v${NEW_VERSION}

- Update CHANGELOG.md
- Update README.md
- Update version numbers"

git push origin release/v${NEW_VERSION}
```

### 6. Pull Request erstellen

Erstelle einen PR von `release/v1.4.0` nach `main`:

- **Titel**: `Release v1.4.0`
- **Labels**: `release`
- **Beschreibung**: Kopiere relevante Teile aus CHANGELOG.md

**Review-Checklist:**
- [ ] CHANGELOG.md vollständig
- [ ] Alle Tests grün
- [ ] Dokumentation aktualisiert
- [ ] Keine Breaking Changes (oder dokumentiert)

### 7. Merge und Tag

Nach Approval:

```bash
# Merge PR zur aktuellen Release-Branch (v1.4)
git checkout v1.4
git pull origin v1.4

# Tag erstellen
git tag -a v${NEW_VERSION} -m "Release v${NEW_VERSION}

- Feature 1
- Feature 2
- Bug fixes"

# Tag pushen
git push origin v${NEW_VERSION}
```

**Hinweis:** Dieses Repo verwendet Branch-basierte Releases (v1.3, v1.4) statt einem zentralen `main` Branch. Passe Befehle entsprechend an.

### 8. GitHub Release erstellen

1. Gehe zu [Releases](https://github.com/arn-c0de/Crawllama/releases)
2. Klicke "Draft a new release"
3. Wähle Tag: `v1.4.0`
4. Release-Titel: `CrawlLama v1.4.0 - Feature Name`
5. Beschreibung:

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
./setup.sh  # oder setup.bat
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

6. Klicke "Publish release"

### 9. Post-Release Tasks

#### a) Announce

- GitHub Discussions: Release Announcement
- Update README badges (optional)

#### b) Monitor

Nach Release für 24-48h überwachen:

```bash
# GitHub Issues prüfen
# Feedback sammeln
# Hotfixes bei Critical Bugs
```

#### c) Hotfix-Process (bei Bedarf)

Falls Critical Bug nach Release:

```bash
# Hotfix Branch
git checkout -b hotfix/v1.4.1 v1.4.0

# Fix implementieren
# Tests hinzufügen

# Commit
git commit -m "fix(critical): description"

# Merge zu main
git checkout main
git merge hotfix/v1.4.1

# Tag
git tag -a v1.4.1 -m "Hotfix v1.4.1"
git push origin v1.4.1

# GitHub Release (wie oben)
```

## Release-Checklist

Vor jedem Release:

### Code
- [ ] Alle Tests grün (`pytest tests/`)
- [ ] Coverage ≥80%
- [ ] Keine Warnungen in Tests
- [ ] Code-Review abgeschlossen

### Security
- [ ] `pip-audit` ohne Critical/High
- [ ] `safety check` ohne Vulnerabilities
- [ ] Keine Secrets im Code
- [ ] `.env.example` hat nur Platzhalter

### Dokumentation
- [ ] README.md aktualisiert
- [ ] CHANGELOG.md vollständig
- [ ] Breaking Changes dokumentiert
- [ ] Migration-Guide (bei Major Release)

### Quality
- [ ] flake8 ohne Errors
- [ ] Type-Hints vollständig (optional)
- [ ] Docstrings aktualisiert
- [ ] Coverage ≥45% (Preview) / ≥80% (Production)

### Git
- [ ] Branch von main erstellt
- [ ] Commit-Messages korrekt (Conventional Commits)
- [ ] PR-Review abgeschlossen

### Release
- [ ] Version-Tag erstellt
- [ ] GitHub Release veröffentlicht
- [ ] Release Notes vollständig

## Rollback-Prozess

Falls Major-Issues nach Release:

```bash
# Revert auf vorherige Version
git revert v1.4.0

# Oder: Git-Reset (bei schwerwiegenden Problemen)
git reset --hard v1.3.0
git push --force origin main

# GitHub Release als "yanked" markieren
# Neuen Hotfix-Release erstellen
```

## Branching-Strategie

```
main                 (production-ready)
  ├── develop        (development)
  │   ├── feature/*  (neue Features)
  │   ├── fix/*      (Bug-Fixes)
  │   └── docs/*     (Dokumentation)
  ├── release/*      (Release-Vorbereitung)
  └── hotfix/*       (Kritische Fixes)
```

**Workflow:**
1. Feature-Branch von `develop`
2. PR zu `develop`
3. Release-Branch von `develop`
4. PR zu `main`
5. Tag auf `main`

## Release-Frequency

- **Patch**: Bei Bedarf (Hotfixes)
- **Minor**: Alle 2-4 Wochen
- **Major**: Alle 3-6 Monate

## Automatisierung (Zukünftig)

Geplante CI/CD-Integration:

```yaml
# .github/workflows/release.yml
# Automatische:
# - Version-Bump
# - CHANGELOG-Update
# - Tests
# - Security-Checks
# - GitHub Release
```

---

**Bei Fragen zum Release-Prozess:** [GitHub Discussions](https://github.com/arn-c0de/Crawllama/discussions)
