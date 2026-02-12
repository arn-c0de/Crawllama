# Configuration Files

## `config.json.example` vs `config.json`

- **`config.json.example`** 
 - Template with default settings 
 - Tracked in Git 

- **`config.json`** 
 - Your personal configuration 
 - **Not tracked in Git** 
 - Stores sensitive data (API keys, custom models, etc.)

> The setup script automatically creates `config.json` from `config.json.example` during the first installation. 
> This ensures personal settings are never accidentally committed.
