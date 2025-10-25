# Notfallplan für Secret-Leaks

---

📚 **Navigation:** [🏠 Home](../../README.md) | [📖 Docs](../README.md) | [🔒 Security](../../SECURITY.md) | [📋 Release](RELEASE_PROCESS.md) | [✅ Pre-Release Check](PRE_RELEASE_CHECK.md)

---

Dieser Leitfaden beschreibt Sofortmaßnahmen bei versehentlichem Commit von Secrets/API-Keys.

## 🚨 Sofortmaßnahmen (innerhalb von 1 Stunde)

### 1. Secret-Typ identifizieren

Bestimme **WAS** geleakt wurde:

- [ ] API-Keys (Brave, Serper, etc.)
- [ ] Ollama-Credentials
- [ ] Database-Credentials
- [ ] Private Keys (SSH, GPG)
- [ ] Tokens (GitHub, OAuth)
- [ ] Passwörter
- [ ] Andere sensible Daten

### 2. Betroffene Secrets SOFORT widerrufen

**API-Keys:**

```bash
# Brave Search API
# https://brave.com/search/api → API Keys → Revoke

# Serper API
# https://serper.dev/dashboard → API Keys → Delete

# GitHub Tokens
# https://github.com/settings/tokens → Delete Token
```

**Passwörter:**

```bash
# ALLE betroffenen Passwörter SOFORT ändern
# ALLE Sessions beenden
```

### 3. Git-History bereinigen

⚠️ **WICHTIG**: Dies ändert die Git-History permanent!

#### Option A: BFG Repo-Cleaner (Empfohlen)

```bash
# BFG installieren
# https://rtyley.github.io/bfg-repo-cleaner/

# Backup erstellen
git clone --mirror https://github.com/arn-c0de/Crawllama.git crawllama-backup

# Secret aus History entfernen
bfg --replace-text passwords.txt crawllama.git

# Beispiel passwords.txt:
# BRAVE_API_KEY=abc123xyz===>BRAVE_API_KEY=***REMOVED***
# SERPER_API_KEY=def456===>SERPER_API_KEY=***REMOVED***

# Git cleanup
cd crawllama.git
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push
git push --force
```

#### Option B: git-filter-repo

```bash
# git-filter-repo installieren
pip install git-filter-repo

# Secret-Pattern definieren
echo "BRAVE_API_KEY=abc123xyz" > secrets.txt

# Aus History entfernen
git filter-repo --replace-text secrets.txt

# Force push
git push --force
```

#### Option C: Manuell (kleine Repos)

```bash
# Nur für kleine Repos / wenige Commits!

# Letzten Commit entfernen
git reset --hard HEAD~1
git push --force

# Oder: Interaktives Rebase
git rebase -i HEAD~10  # Letzte 10 Commits
# "drop" bei betroffenen Commits
git push --force
```

### 4. Neue Secrets generieren

```bash
# Neue API-Keys generieren
# In .env eintragen
echo "BRAVE_API_KEY=new_key_here" >> .env
echo "SERPER_API_KEY=new_key_here" >> .env

# .env zu .gitignore hinzufügen (falls noch nicht)
echo ".env" >> .gitignore
git add .gitignore
git commit -m "chore: ensure .env is in .gitignore"
```

### 5. Alle Collaborators informieren

```bash
# GitHub Security Advisory erstellen
# https://github.com/arn-c0de/Crawllama/security/advisories

# Oder: GitHub Issue (private)
```

**Benachrichtigung:**

```markdown
🚨 CRITICAL: Secret Leak - Action Required

A secret was accidentally committed to the repository.

**Affected:**
- API Key: Brave Search API
- Commit: abc123
- Exposed: 2025-01-25 10:30 UTC

**Actions Taken:**
✅ Secret revoked immediately
✅ Git history cleaned
✅ New secret generated

**Required Actions:**
- Pull latest changes: `git pull --rebase`
- Update your .env with new keys
- Verify no local copies of old keys

**Timeline:**
- 10:30 - Leak discovered
- 10:35 - Secret revoked
- 10:45 - History cleaned
- 11:00 - New secret deployed
```

## 📋 Prävention

### Pre-Commit Hooks

Installiere Pre-Commit Hooks zur automatischen Secret-Erkennung:

```bash
# pre-commit installieren
pip install pre-commit

# .pre-commit-config.yaml erstellen
cat > .pre-commit-config.yaml << EOF
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: detect-private-key
      - id: check-added-large-files
        args: ['--maxkb=1000']
      
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
EOF

# Installieren
pre-commit install

# Baseline erstellen
detect-secrets scan > .secrets.baseline
```

### .gitignore pflegen

```bash
# Stelle sicher, dass sensible Dateien ignoriert werden
cat >> .gitignore << EOF

# Secrets
.env
*.key
*.pem
*.p12
*.pfx
secrets/
credentials/

# Backups
*.backup
*.bak
*~

# Logs mit potentiellen Secrets
logs/*.log
EOF
```

### Secret-Scanner in CI/CD

```yaml
# .github/workflows/secret-scan.yml
name: Secret Scan

on: [push, pull_request]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0
      
      - name: Run Gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### .env.example pflegen

```bash
# Stelle sicher, dass .env.example NUR Platzhalter hat
cat > .env.example << EOF
# API Keys (get from providers)
BRAVE_API_KEY=your_brave_api_key_here
SERPER_API_KEY=your_serper_api_key_here

# Proxy (optional)
HTTP_PROXY=
HTTPS_PROXY=

# Debug
DEBUG=false
EOF
```

## 🔍 Secret-Leak erkennen

### GitHub Secret Scanning

GitHub scannt automatisch nach bekannten Secret-Patterns:

- ✅ Automatische Alerts bei bekannten Patterns
- ✅ Partner-Notifications (z.B. AWS benachrichtigt bei AWS-Keys)
- ✅ Secret-Scanning-Alerts in Security-Tab

**Aktivieren:**

1. Repository → Settings → Security → Code security and analysis
2. Secret scanning → Enable

### Manuelle Suche

```bash
# Suche nach potentiellen Secrets in History
git log -S "BRAVE_API_KEY" --all
git log -S "password" --all
git log -S "secret" --all

# Suche in aktuellen Dateien
grep -r "BRAVE_API_KEY" .
grep -r "password" .
grep -r "BEGIN.*PRIVATE KEY" .
```

### Gitleaks (lokal)

```bash
# Gitleaks installieren
# https://github.com/gitleaks/gitleaks

# Scan durchführen
gitleaks detect --source . --verbose

# Scan mit Report
gitleaks detect --source . --report-path gitleaks-report.json
```

## 📞 Incident-Response-Team

Bei kritischen Leaks:

| Rolle | Verantwortung | Kontakt |
|-------|---------------|---------|
| Security Lead | Koordination | [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com) |
| DevOps | History-Cleanup | [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com) |
| API-Owner | Key-Rotation | Service-Provider |

**Für Secret-Leaks kontaktiere bitte umgehend:**  
📧 [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com) (verschlüsselt via Proton Mail)

## 📊 Post-Incident Review

Nach Secret-Leak:

### 1. Incident-Report erstellen

```markdown
# Incident Report: Secret Leak

**Date:** 2025-01-25
**Severity:** HIGH
**Status:** RESOLVED

## Summary
API Key for Brave Search was accidentally committed.

## Timeline
- 10:30 - Commit with secret pushed
- 10:32 - Leak detected by GitHub Scanner
- 10:35 - Secret revoked
- 10:45 - Git history cleaned
- 11:00 - New secret deployed
- 11:15 - All systems operational

## Root Cause
Developer used .env file without checking .gitignore

## Impact
- 5 minutes of potential exposure
- No evidence of unauthorized use
- All logs reviewed

## Actions Taken
✅ Secret revoked immediately
✅ Git history cleaned with BFG
✅ New secret generated
✅ Team notified
✅ Pre-commit hooks installed

## Prevention
- Pre-commit hooks mandatory
- Developer training scheduled
- .gitignore review completed
```

### 2. Lessons Learned

- Was lief gut?
- Was lief schlecht?
- Was verbessern wir?

### 3. Präventionsmaßnahmen

- [ ] Pre-Commit Hooks für alle Entwickler
- [ ] Secret-Scanner in CI/CD
- [ ] Regelmäßige Security-Reviews
- [ ] Developer-Training
- [ ] .env.example aktuell halten

## 🔗 Nützliche Tools

| Tool | Zweck | Link |
|------|-------|------|
| BFG Repo-Cleaner | Git History Cleaning | [GitHub](https://rtyley.github.io/bfg-repo-cleaner/) |
| git-filter-repo | Advanced History Rewriting | [GitHub](https://github.com/newren/git-filter-repo) |
| Gitleaks | Secret Detection | [GitHub](https://github.com/gitleaks/gitleaks) |
| detect-secrets | Pre-Commit Hook | [GitHub](https://github.com/Yelp/detect-secrets) |
| truffleHog | Secret Scanner | [GitHub](https://github.com/trufflesecurity/trufflehog) |

## 📚 Weitere Ressourcen

- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning)
- [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_CheatSheet.html)
- [Git History Rewriting](https://git-scm.com/book/en/v2/Git-Tools-Rewriting-History)

---

**Bei aktiven Leaks:** [Security Advisory melden](https://github.com/arn-c0de/Crawllama/security/advisories)
