"""Secure configuration management for API keys and sensitive data."""
import os
import json
from pathlib import Path
from typing import Dict, Optional
from cryptography.fernet import Fernet
from dotenv import load_dotenv, set_key


class SecureConfig:
    """Manage API keys and sensitive configuration securely."""

    def __init__(self, env_path: str = ".env"):
        """
        Initialize secure config manager.

        Args:
            env_path: Path to .env file
        """
        self.env_path = Path(env_path)
        self.encryption_key_path = Path(".encryption_key")
        load_dotenv(self.env_path)

    def _get_or_create_encryption_key(self) -> bytes:
        """
        Get or create encryption key.

        Returns:
            Encryption key bytes
        """
        if self.encryption_key_path.exists():
            with open(self.encryption_key_path, "rb") as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(self.encryption_key_path, "wb") as f:
                f.write(key)
            # Make file hidden on Windows
            if os.name == 'nt':
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(
                    str(self.encryption_key_path), 2
                )
            return key

    def encrypt_value(self, value: str) -> str:
        """
        Encrypt a value.

        Args:
            value: Value to encrypt

        Returns:
            Encrypted value as string
        """
        key = self._get_or_create_encryption_key()
        f = Fernet(key)
        return f.encrypt(value.encode()).decode()

    def decrypt_value(self, encrypted_value: str) -> str:
        """
        Decrypt a value.

        Args:
            encrypted_value: Encrypted value

        Returns:
            Decrypted value
        """
        key = self._get_or_create_encryption_key()
        f = Fernet(key)
        return f.decrypt(encrypted_value.encode()).decode()

    def set_api_key(self, key_name: str, key_value: str, encrypt: bool = False):
        """
        Set an API key in .env file.

        Args:
            key_name: Name of the key (e.g., 'SERPER_API_KEY')
            key_value: Value of the key
            encrypt: Whether to encrypt the value
        """
        if encrypt:
            key_value = self.encrypt_value(key_value)
            key_name = f"{key_name}_ENCRYPTED"

        # Create .env if it doesn't exist
        if not self.env_path.exists():
            self.env_path.touch()

        set_key(self.env_path, key_name, key_value)

    def get_api_key(self, key_name: str, encrypted: bool = False) -> Optional[str]:
        """
        Get an API key from environment.

        Args:
            key_name: Name of the key
            encrypted: Whether the key is encrypted

        Returns:
            API key value or None
        """
        if encrypted:
            key_name = f"{key_name}_ENCRYPTED"

        value = os.getenv(key_name)
        if value and encrypted:
            try:
                return self.decrypt_value(value)
            except Exception:
                return None
        return value

    def validate_keys(self) -> Dict[str, bool]:
        """
        Validate all configured API keys.

        Returns:
            Dictionary with key names and validation status
        """
        keys_to_check = [
            "SERPER_API_KEY",
            "BRAVE_API_KEY",
            "OPENAI_API_KEY"
        ]

        results = {}
        for key in keys_to_check:
            value = self.get_api_key(key)
            encrypted_value = self.get_api_key(key, encrypted=True)
            results[key] = bool(value or encrypted_value)

        return results

    def setup_interactive(self):
        """Run interactive setup for API keys."""
        from rich.console import Console
        from rich.prompt import Prompt, Confirm

        console = Console()
        console.print("\n[bold cyan]API Key Setup[/bold cyan]")
        console.print("Configure your API keys for external services.\n")

        keys_config = {
            "SERPER_API_KEY": {
                "description": "Serper API (for Google Search)",
                "url": "https://serper.dev",
                "optional": True
            },
            "BRAVE_API_KEY": {
                "description": "Brave Search API",
                "url": "https://brave.com/search/api/",
                "optional": True
            },
            "OPENAI_API_KEY": {
                "description": "OpenAI API (for embeddings)",
                "url": "https://platform.openai.com",
                "optional": True
            }
        }

        for key_name, config in keys_config.items():
            console.print(f"\n[yellow]{config['description']}[/yellow]")
            console.print(f"[dim]Get your key at: {config['url']}[/dim]")

            current_value = self.get_api_key(key_name)
            if current_value:
                console.print("[green]✓ Already configured[/green]")
                if not Confirm.ask("Update?", default=False):
                    continue

            key_value = Prompt.ask(
                f"Enter {key_name}",
                default="skip" if config['optional'] else None,
                password=True
            )

            if key_value and key_value != "skip":
                encrypt = Confirm.ask("Encrypt this key?", default=True)
                self.set_api_key(key_name, key_value, encrypt=encrypt)
                console.print("[green]✓ Saved[/green]")
            elif config['optional']:
                console.print("[dim]Skipped (optional)[/dim]")

        console.print("\n[green]Setup complete![/green]")

        # Show validation results
        console.print("\n[bold]Validation:[/bold]")
        results = self.validate_keys()
        for key, valid in results.items():
            status = "[green]✓[/green]" if valid else "[red]✗[/red]"
            console.print(f"{status} {key}")


def load_from_env() -> Dict[str, Optional[str]]:
    """
    Load all API keys from environment.

    Returns:
        Dictionary with key names and values
    """
    config = SecureConfig()
    keys = ["SERPER_API_KEY", "BRAVE_API_KEY", "OPENAI_API_KEY"]

    result = {}
    for key in keys:
        value = config.get_api_key(key)
        if not value:
            value = config.get_api_key(key, encrypted=True)
        result[key] = value

    return result
