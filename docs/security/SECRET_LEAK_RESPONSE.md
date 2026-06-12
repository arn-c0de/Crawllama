# Emergency Plan for Secret Leaks

---

 **Navigation:** [Home](../../README.md) | [Docs](../README.md) | [Security](../../SECURITY.md)

---

This guide describes immediate actions for accidental commits of secrets or API keys.

## Immediate Actions (within 1 hour)

### 1. Identify Secret Type

Determine **what** was leaked:

- [] API keys (Brave, Serper, etc.) 
- [] Ollama credentials 
- [] Database credentials 
- [] Private keys (SSH, GPG) 
- [] Tokens (GitHub, OAuth) 
- [] Passwords 
- [] Other sensitive data 

### 2. Revoke Affected Secrets IMMEDIATELY

**API Keys:** 

```bash
# Brave Search API
# https://brave.com/search/api → Revoke

# Serper API
# https://serper.dev/dashboard → Delete

# GitHub Tokens
# https://github.com/settings/tokens → Delete Token
````

**Passwords:**

```bash
# Change ALL affected passwords immediately
# End ALL sessions
```

### 3. Clean Git History

 **Important:** Permanently changes Git history!

#### Option A: BFG Repo-Cleaner (Recommended)

```bash
git clone --mirror https://github.com/arn-c0de/Crawllama.git crawllama-backup.git
bfg --replace-text passwords.txt crawllama-backup.git
cd crawllama-backup.git
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push --force
```

#### Option B: git-filter-repo

```bash
pip install git-filter-repo
echo "BRAVE_API_KEY=abc123xyz" > secrets.txt
git filter-repo --replace-text secrets.txt
git push --force
```

#### Option C: Manual (small repos)

```bash
git reset --hard HEAD~1
git push --force
# or interactive rebase
git rebase -i HEAD~10
# "drop" affected commits
git push --force
```

### 4. Generate New Secrets

```bash
# Generate new API keys
echo "BRAVE_API_KEY=new_key_here" >> .env
echo "SERPER_API_KEY=new_key_here" >> .env

# Ensure .env is ignored
echo ".env" >> .gitignore
git add .gitignore
git commit -m "chore: ensure .env is in .gitignore"
```

### 5. Inform All Collaborators

Create GitHub Security Advisory or private issue. Example notification:

```markdown
 CRITICAL: Secret Leak

A secret was accidentally committed.

**Affected:** 
- API Key: Brave Search API 
- Commit: abc123 
- Exposed: 2025-01-25 10:30 UTC

**Actions Taken:** 
 Secret revoked 
 Git history cleaned 
 New secret generated 

**Required Actions:** 
- Pull latest changes 
- Update .env with new keys 
- Verify no local copies of old keys
```

---

## Prevention

### Pre-Commit Hooks

```bash
pip install pre-commit
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
pre-commit install
detect-secrets scan > .secrets.baseline
```

### Maintain .gitignore

```bash
cat >> .gitignore << EOF
.env
*.key
*.pem
*.p12
*.pfx
secrets/
credentials/
*.backup
*.bak
*~
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

### Maintain `.env.example`

```bash
cat > .env.example << EOF
BRAVE_API_KEY=your_brave_api_key_here
SERPER_API_KEY=your_serper_api_key_here
HTTP_PROXY=
HTTPS_PROXY=
DEBUG=false
EOF
```

---

## Detect Secret Leaks

### GitHub Secret Scanning

* Automatic alerts for known patterns
* Partner notifications for sensitive keys
* Enable via: Settings → Security → Secret scanning

### Manual Search

```bash
git log -S "BRAVE_API_KEY" --all
grep -r "password" .
grep -r "BEGIN.*PRIVATE KEY" .
```

### Gitleaks (local)

```bash
gitleaks detect --source . --verbose
gitleaks detect --source . --report-path gitleaks-report.json
```

---

## Incident Response Team | Role | Responsibility | Contact |
| ------------- | --------------- | --------------------------------------------------------------------------- |
| Security Lead | Coordination | [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com) |
| DevOps | History cleanup | [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com) |
| API Owner | Key rotation | Service provider |

**Contact immediately for leaks:** [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com)

---

## Post-Incident Review

### 1. Incident Report

```markdown
# Incident Report: Secret Leak
**Date:** 2025-01-25
**Severity:** HIGH
**Status:** RESOLVED

## Summary
API Key accidentally committed.

## Timeline
10:30 - Commit with secret pushed 
10:32 - Leak detected 
10:35 - Secret revoked 
10:45 - Git history cleaned 
11:00 - New secret deployed 
11:15 - All systems operational

## Root Cause
.env not checked in .gitignore

## Actions Taken
 Secret revoked 
 Git history cleaned 
 New secret generated 
 Team notified 
 Pre-commit hooks installed

## Prevention
- Pre-commit hooks mandatory
- Developer training
- .gitignore review
```

### 2. Lessons Learned

* Identify what went well
* Identify what went poorly
* Plan improvements

### 3. Prevention Measures

* [] Pre-commit hooks
* [] CI/CD secret scanning
* [] Regular security reviews
* [] Developer training
* [] Keep `.env.example` current

---

## Useful Tools | Tool | Purpose | Link |
| ---------------- | ------------------------ | ------------------------------------------------------- |
| BFG Repo-Cleaner | Git history cleanup | [GitHub](https://rtyley.github.io/bfg-repo-cleaner/) |
| git-filter-repo | Advanced history rewrite | [GitHub](https://github.com/newren/git-filter-repo) |
| Gitleaks | Secret detection | [GitHub](https://github.com/gitleaks/gitleaks) |
| detect-secrets | Pre-commit hook | [GitHub](https://github.com/Yelp/detect-secrets) |
| truffleHog | Secret scanner | [GitHub](https://github.com/trufflesecurity/trufflehog) |

---

## Further Resources

* [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning)
* [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_CheatSheet.html)
* [Git History Rewriting](https://git-scm.com/book/en/v2/Git-Tools-Rewriting-History)

---

**For active leaks:** [Report Security Advisory](https://github.com/arn-c0de/Crawllama/security/advisories)

