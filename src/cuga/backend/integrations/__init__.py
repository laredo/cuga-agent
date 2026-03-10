"""Generic integration system for CUGA

This module provides a clean interface for registering external integrations
without polluting the main CUGA codebase with integration-specific code.
"""

import os
from typing import Optional, Callable, Any
from loguru import logger


class IntegrationRegistry:
    """Registry for managing external integrations"""
    
    def __init__(self):
        self._integrations = {}
        self._initialized = False
    
    async def initialize_all(self, app: Any) -> None:
        """Initialize all enabled integrations
        
        Args:
            app: FastAPI application instance
        """
        if self._initialized:
            return
        
        # Check for Slack integration
        if os.getenv("CUGA_SLACK_ENABLE", "false").lower() in ("true", "1", "yes", "on"):
            try:
                from cuga.backend.integrations.slack.setup import setup_slack_integration
                await setup_slack_integration(app)
                self._integrations["slack"] = True
                logger.info("✅ Slack integration registered")
            except Exception as e:
                logger.error(f"Failed to initialize Slack integration: {e}")
        
        # Future integrations can be added here:
        # if os.getenv("CUGA_TEAMS_ENABLE", "false").lower() in ("true", "1", "yes", "on"):
        #     from cuga.backend.integrations.teams.setup import setup_teams_integration
        #     await setup_teams_integration(app)
        
        self._initialized = True
        
        if not self._integrations:
            logger.info("No integrations enabled")
    
    async def shutdown_all(self) -> None:
        """Shutdown all integrations"""
        # Future: call shutdown hooks for each integration
        self._integrations.clear()
        self._initialized = False


# Global registry instance
integration_registry = IntegrationRegistry()


async def initialize_integrations(app: Any) -> None:
    """Initialize all enabled integrations
    
    This is the main entry point called from the CUGA server lifespan.
    
    Args:
        app: FastAPI application instance
    """
    await integration_registry.initialize_all(app)


async def shutdown_integrations() -> None:
    """Shutdown all integrations"""
    await integration_registry.shutdown_all()

# Made with Bob
