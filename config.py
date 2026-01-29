"""
7000%AUTO Configuration Module
Environment-based configuration using Pydantic Settings
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "7000%AUTO"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # OpenCode AI Settings (Required - no defaults)
    # Users MUST set these environment variables:
    #   OPENCODE_API_KEY   - API key for your AI provider
    #   OPENCODE_API_BASE  - API base URL (e.g. https://api.minimax.io/anthropic/v1)
    #   OPENCODE_SDK       - AI SDK npm package (e.g. @ai-sdk/anthropic, @ai-sdk/openai)
    #   OPENCODE_MODEL     - Model name (e.g. MiniMax-M2.1, gpt-4o)
    #   OPENCODE_MAX_TOKENS - Max output tokens (e.g. 196608)
    OPENCODE_API_KEY: str = Field(default="", description="API key for your AI provider (REQUIRED)")
    OPENCODE_API_BASE: str = Field(default="", description="API base URL (REQUIRED)")
    OPENCODE_SDK: str = Field(default="", description="AI SDK npm package (REQUIRED, e.g. @ai-sdk/anthropic, @ai-sdk/openai)")
    OPENCODE_MODEL: str = Field(default="", description="Model name to use (REQUIRED)")
    OPENCODE_MAX_TOKENS: int = Field(default=0, description="Maximum output tokens for AI responses (REQUIRED)")
    
    # OpenCode Server
    OPENCODE_SERVER_URL: Optional[str] = Field(default=None, description="OpenCode server URL (default: http://127.0.0.1:18080)")
    
    # GitHub
    GITHUB_TOKEN: str = Field(default="", description="GitHub Personal Access Token")
    GITHUB_USERNAME: Optional[str] = Field(default=None, description="GitHub username for repo creation")
    
    # X (Twitter) API
    X_API_KEY: str = Field(default="", description="X API Key (Consumer Key)")
    X_API_SECRET: str = Field(default="", description="X API Secret (Consumer Secret)")
    X_ACCESS_TOKEN: str = Field(default="", description="X Access Token")
    X_ACCESS_TOKEN_SECRET: str = Field(default="", description="X Access Token Secret")
    X_BEARER_TOKEN: Optional[str] = Field(default=None, description="X Bearer Token for API v2")
    
    # Database
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./data/7000auto.db",
        description="Database connection URL"
    )
    DATABASE_ECHO: bool = Field(default=False, description="Echo SQL queries")
    
    # Workspace
    WORKSPACE_DIR: Path = Field(
        default=Path("./workspace"),
        description="Directory for project workspaces"
    )
    
    # Web Server
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8000, description="Server port")
    
    # Orchestrator
    AUTO_START: bool = Field(default=True, description="Auto-start orchestrator on boot")
    MAX_CONCURRENT_PROJECTS: int = Field(default=1, description="Max concurrent projects")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"
    
    def ensure_directories(self):
        """Create necessary directories"""
        self.WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        Path("./data").mkdir(parents=True, exist_ok=True)
    
    @property
    def is_github_configured(self) -> bool:
        return bool(self.GITHUB_TOKEN)
    
    @property
    def is_x_configured(self) -> bool:
        return all([
            self.X_API_KEY,
            self.X_API_SECRET,
            self.X_ACCESS_TOKEN,
            self.X_ACCESS_TOKEN_SECRET
        ])
    
    @property
    def is_opencode_configured(self) -> bool:
        """Check if all required OpenCode settings are configured"""
        return all([
            self.OPENCODE_API_KEY,
            self.OPENCODE_API_BASE,
            self.OPENCODE_SDK,
            self.OPENCODE_MODEL,
            self.OPENCODE_MAX_TOKENS > 0,
        ])
    
    def get_missing_opencode_settings(self) -> list[str]:
        """Return list of missing required OpenCode settings"""
        missing = []
        if not self.OPENCODE_API_KEY:
            missing.append("OPENCODE_API_KEY")
        if not self.OPENCODE_API_BASE:
            missing.append("OPENCODE_API_BASE")
        if not self.OPENCODE_SDK:
            missing.append("OPENCODE_SDK")
        if not self.OPENCODE_MODEL:
            missing.append("OPENCODE_MODEL")
        if self.OPENCODE_MAX_TOKENS <= 0:
            missing.append("OPENCODE_MAX_TOKENS")
        return missing


# Global settings instance
settings = Settings()
