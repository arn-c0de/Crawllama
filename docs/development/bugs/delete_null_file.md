# Deleting a File Named `NUL` on Windows

Sometimes, due to a bug, files with reserved names like `NUL`, `CON`, `PRN`, `AUX`, `COM1–COM9`, or `LPT1–LPT9` may appear and cannot be deleted normally.

> These names are reserved by Windows for devices, so normal delete operations fail. It is usually caused by a software bug, archive extraction, or script error — **not a virus**.

## Root Cause in CrawlLama

The `nul` file can be created by Windows batch scripts that use lowercase `>nul` for output redirection. Under certain conditions (crashes, wrong working directory, Unicode path issues), Windows may create a file named `nul` instead of redirecting to the NUL device.

### Prevention (v1.4.6+)

All batch scripts now include:
1. **Uppercase redirection**: Changed `>nul` to `>NUL` (more reliable on Windows)
2. **Auto-cleanup**: Each batch script removes any existing `nul` file on startup
3. **Manual cleanup**: Run `cleanup_nul.bat` if the file appears

The fix was applied to:
- `setup.bat` (lines 5, 10, 108)
- `run.bat` (line 6)
- `run_api.bat` (line 6)
- `health-dashboard.bat` (line 6)

## Steps to Delete

### 1. Using the UNC Path
Open **Command Prompt as Administrator**:

```cmd
del "\\?\C:\Path\To\Folder\NUL"
````

### 2. Rename then Delete

```cmd
ren "\\?\C:\Path\To\Folder\NUL" temp.txt
del "\\?\C:\Path\To\Folder\temp.txt"
```

### 3. Using Linux/WSL

```bash
rm /mnt/c/Path/To/Folder/NUL
```

**Tip:** Always use the full path with `\\?\` to handle reserved filenames.
