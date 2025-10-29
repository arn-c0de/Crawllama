# Configuration Files

## config.json vs config.json.example

- **config.json.example**: Template with default settings (tracked in git)
- **config.json**: Your personal configuration (NOT tracked in git)

The setup script automatically creates config.json from config.json.example on first install.
This prevents accidental commits of personal settings (API keys, custom models, etc.).
