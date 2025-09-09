"""
Centralized Token Management for the Hive
SECURITY: Never store actual tokens here. Use environment variables or GitHub Secrets.
"""

import os
from typing import Optional

class TokenVault:
    """
    Central vault for all API tokens and secrets.
    Reads from environment variables, with fallback to GitHub Secrets in CI/CD.
    """
    
    @staticmethod
    def get(key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a token from environment variables."""
        return os.environ.get(key, default)
    
    # API Keys - Will be loaded from environment or GitHub Secrets
    @property
    def OPENAI_API_KEY(self) -> Optional[str]:
        return self.get("OPENAI_API_KEY")
    
    @property
    def ANTHROPIC_API_KEY(self) -> Optional[str]:
        return self.get("ANTHROPIC_API_KEY")
    
    @property
    def GOOGLE_API_KEY(self) -> Optional[str]:
        return self.get("GOOGLE_API_KEY")
    
    @property
    def GEMINI_API_KEY(self) -> Optional[str]:
        return self.get("GEMINI_API_KEY")
    
    @property
    def AIRTABLE_API_KEY(self) -> Optional[str]:
        return self.get("AIRTABLE_API_KEY")
    
    @property
    def AIRTABLE_BASE(self) -> Optional[str]:
        return self.get("AIRTABLE_BASE")
    
    # MCP Server Keys
    @property
    def BROWSERBASE_API_KEY(self) -> Optional[str]:
        return self.get("BROWSERBASE_API_KEY")
    
    @property
    def BROWSERBASE_PROJECT_ID(self) -> Optional[str]:
        return self.get("BROWSERBASE_PROJECT_ID")
    
    @property
    def MAGIC_API_KEY(self) -> Optional[str]:
        return self.get("MAGIC_API_KEY")
    
    @property
    def LINKUP_API_KEY(self) -> Optional[str]:
        return self.get("LINKUP_API_KEY")
    
    @property
    def EXA_API_KEY(self) -> Optional[str]:
        return self.get("EXA_API_KEY")
    
    @property
    def FIRECRAWL_API_KEY(self) -> Optional[str]:
        return self.get("FIRECRAWL_API_KEY")
    
    @property
    def OPIK_API_KEY(self) -> Optional[str]:
        return self.get("OPIK_API_KEY")
    
    # Service-specific tokens
    @property
    def TELEGRAM_BOT_TOKEN(self) -> Optional[str]:
        return self.get("TELEGRAM_BOT_TOKEN")
    
    @property
    def TELEGRAM_ADMIN_BOT_TOKEN(self) -> Optional[str]:
        return self.get("TELEGRAM_ADMIN_BOT_TOKEN")
    
    @property
    def UNSPLASH_API_KEY(self) -> Optional[str]:
        return self.get("UNSPLASH_API_KEY")
    
    @property
    def OPENWEATHER_API_KEY(self) -> Optional[str]:
        return self.get("OPENWEATHER_API_KEY")
    
    # Google Services
    @property
    def GOOGLE_CLIENT_ID(self) -> Optional[str]:
        return self.get("GOOGLE_CLIENT_ID")
    
    @property
    def GOOGLE_CLIENT_SECRET(self) -> Optional[str]:
        return self.get("GOOGLE_CLIENT_SECRET")
    
    @property
    def GMAPS_API_KEY(self) -> Optional[str]:
        return self.get("GMAPS_API_KEY")
    
    @property
    def SEARCH_ENGINE_ID(self) -> Optional[str]:
        return self.get("SEARCH_ENGINE_ID")
    
    def validate_required_tokens(self, required: list[str]) -> bool:
        """Validate that required tokens are present."""
        missing = []
        for token_name in required:
            if not getattr(self, token_name, None):
                missing.append(token_name)
        
        if missing:
            print(f"⚠️ Missing required tokens: {', '.join(missing)}")
            print("Set these in your environment or GitHub Secrets")
            return False
        return True


# Global instance
vault = TokenVault()