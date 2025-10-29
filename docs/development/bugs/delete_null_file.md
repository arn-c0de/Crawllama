# Deleting a File Named `NUL` on Windows

Sometimes, due to a bug, files with reserved names like `NUL`, `CON`, `PRN`, `AUX`, `COM1–COM9`, or `LPT1–LPT9` may appear and cannot be deleted normally.  

> These names are reserved by Windows for devices, so normal delete operations fail. It is usually caused by a software bug, archive extraction, or script error — **not a virus**.

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
