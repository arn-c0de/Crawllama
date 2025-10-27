# Emergency Plan for Secret Leaks

---

📚 **Navigation:** [🏠 Home](../../README.md) | [📖 Docs](../README.md) | [🔒 Security](../../SECURITY.md) | [📋 Release](../development/RELEASE_PROCESS.md) | [✅ Pre-Release Check](../development/PRE_RELEASE_CHECK.md)

---

This guide describes immediate actions for accidental commit of secrets/API keys.

## 🚨 Immediate Actions (within 1 hour)

### 1. Identify Secret Type

Determine **WHAT** was leaked:

- [ ] API keys (Brave, Serper, etc.)
- [ ] Ollama credentials
- [ ] Database credentials
- [ ] Private keys (SSH, GPG)
- [ ] Tokens (GitHub, OAuth)
- [ ] Passwords
- [ ] Other sensitive data

### 2. Revoke Affected Secrets IMMEDIATELY

**API Keys:**

```bash
# Brave Search API
# https://brave.com/search/api → API Keys → Revoke

# Serper API
# https://serper.dev/dashboard → API Keys → Delete

# GitHub Tokens
# https://github.com/settings/tokens → Delete Token
```

**Passwords:**

```bash
# Change ALL affected passwords IMMEDIATELY
# End ALL sessions
```

### 3. Clean Git History

⚠️ **IMPORTANT**: This permanently changes Git history!

#### Option A: BFG Repo-Cleaner (Recommended)

```bash
# Install BFG
# https://rtyley.github.io/bfg-repo-cleaner/

# Create backup
git clone --mirror https://github.com/arn-c0de/Crawllama.git crawllama-backup

# Remove secret from history
bfg --replace-text passwords.txt crawllama.git

# Example passwords.txt:
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
# Install git-filter-repo
pip install git-filter-repo

# Define secret pattern
echo "BRAVE_API_KEY=abc123xyz" > secrets.txt

# Remove from history
git filter-repo --replace-text secrets.txt

# Force push
git push --force
```

#### Option C: Manual (small repos)

```bash
# Only for small repos / few commits!

# Remove last commit
git reset --hard HEAD~1
git push --force

# Or: Interactive rebase
git rebase -i HEAD~10  # Last 10 commits
# "drop" for affected commits
git push --force
```

### 4. Generate New Secrets

```bash
# Generate new API keys
# Add to .env
echo "BRAVE_API_KEY=new_key_here" >> .env
echo "SERPER_API_KEY=new_key_here" >> .env

# Add .env to .gitignore (if not already)
echo ".env" >> .gitignore
git add .gitignore
git commit -m "chore: ensure .env is in .gitignore"
```

### 5. Inform All Collaborators

```bash
# Create GitHub Security Advisory
# https://github.com/arn-c0de/Crawllama/security/advisories

# Or: GitHub Issue (private)
```

**Notification:**

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

## 📋 Prevention

### Pre-Commit Hooks

Install pre-commit hooks for automatic secret detection:

```bash
# Install pre-commit
pip install pre-commit

# Create .pre-commit-config.yaml
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

# Install
pre-commit install

# Create baseline
detect-secrets scan > .secrets.baseline
```

### Maintain .gitignore

```bash
# Ensure sensitive files are ignored
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

# Logs with potential secrets
logs/*.log
EOF
```

### Secret Scanner in CI/CD

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

### Maintain .env.example

```bash
# Ensure .env.example has ONLY placeholders
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

## 🔍 Detect Secret Leaks

### GitHub Secret Scanning

GitHub automatically scans for known secret patterns:

- ✅ Automatic alerts for known patterns
- ✅ Partner notifications (e.g., AWS notifies for AWS keys)
- ✅ Secret scanning alerts in Security tab

**Enable:**

1. Repository → Settings → Security → Code security and analysis
2. Secret scanning → Enable

### Manual Search

```bash
# Search for potential secrets in history
git log -S "BRAVE_API_KEY" --all
git log -S "password" --all
git log -S "secret" --all

# Search in current files
grep -r "BRAVE_API_KEY" .
grep -r "password" .
grep -r "BEGIN.*PRIVATE KEY" .
```

### Gitleaks (local)

```bash
# Install Gitleaks
# https://github.com/gitleaks/gitleaks

# Run scan
gitleaks detect --source . --verbose

# Scan with report
gitleaks detect --source . --report-path gitleaks-report.json
```

## 📞 Incident Response Team

For critical leaks:

| Role | Responsibility | Contact |
|-------|---------------|---------|
| Security Lead | Coordination | [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com) |
| DevOps | History cleanup | [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com) |
| API Owner | Key rotation | Service provider |

**For secret leaks, please contact immediately:**
📧 [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com) (encrypted via Proton Mail)

## 📊 Post-Incident Review

After secret leak:

### 1. Create Incident Report

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

- What went well?
- What went poorly?
- What will we improve?

### 3. Prevention Measures

- [ ] Pre-commit hooks for all developers
- [ ] Secret scanner in CI/CD
- [ ] Regular security reviews
- [ ] Developer training
- [ ] Keep .env.example current

## 🔗 Useful Tools

| Tool | Purpose | Link |
|------|-------|------|
| BFG Repo-Cleaner | Git history cleaning | [GitHub](https://rtyley.github.io/bfg-repo-cleaner/) |
| git-filter-repo | Advanced history rewriting | [GitHub](https://github.com/newren/git-filter-repo) |
| Gitleaks | Secret detection | [GitHub](https://github.com/gitleaks/gitleaks) |
| detect-secrets | Pre-commit hook | [GitHub](https://github.com/Yelp/detect-secrets) |
| truffleHog | Secret scanner | [GitHub](https://github.com/trufflesecurity/trufflehog) |

## 📚 Further Resources

- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning)
- [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_CheatSheet.html)
- [Git History Rewriting](https://git-scm.com/book/en/v2/Git-Tools-Rewriting-History)

---

**For active leaks:** [Report Security Advisory](https://github.com/arn-c0de/Crawllama/security/advisories)
