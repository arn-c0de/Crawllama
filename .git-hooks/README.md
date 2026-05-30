# CodeQL Pre-commit Hook Installation

## Automatic Installation

### Windows:
```powershell
.\scripts\install-hooks.bat
```

### Linux/Mac:
```bash
./scripts/install-hooks.sh
```

## Manual Installation

### Windows:
```powershell
copy .git-hooks\pre-commit.bat .git\hooks\pre-commit
```

### Linux/Mac:
```bash
cp .git-hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## Features

- Automatic CodeQL security scanning before each commit and before each push
- Blocks commits/pushes with high severity security issues
- Can be bypassed with `git commit --no-verify` or `git push --no-verify` if needed
- Provides SARIF output for detailed analysis

## Requirements

- CodeQL CLI must be installed and in PATH
- Download from: https://github.com/github/codeql-cli-binaries/releases
