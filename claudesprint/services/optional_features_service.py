"""Service for detecting and managing optional MCP dependencies.

This module provides centralized detection and management of optional features
like agent-browser and context7 that enhance ClaudeSprint but aren't required
for basic functionality.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Literal

logger = logging.getLogger(__name__)


class FeatureStatus(str, Enum):
    """Status of an optional feature."""

    AVAILABLE = "available"
    NOT_AVAILABLE = "not_available"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class OptionalFeature:
    """Definition of an optional feature.

    Attributes:
        name: Internal identifier (e.g., "agent-browser", "context7")
        display_name: Human-readable name (e.g., "Browser Automation")
        description: Brief description of what the feature provides
        detection_type: How to detect if feature is available ("npm" or "binary")
        detection_target: Package or binary name to check for
        skill_name: Name of the skill directory to create (if any)
        plugin_key: Key for enabledPlugins in settings.json (if any)
        install_hint: Instructions for installing the feature
    """

    name: str
    display_name: str
    description: str
    detection_type: Literal["npm", "binary"]
    detection_target: str
    skill_name: str | None
    plugin_key: str | None
    install_hint: str


# Registry of all optional features
OPTIONAL_FEATURES: tuple[OptionalFeature, ...] = (
    OptionalFeature(
        name="agent-browser",
        display_name="Browser Automation",
        description="E2E testing with browser automation",
        detection_type="npm",
        detection_target="agent-browser",
        skill_name="agent-browser",
        plugin_key=None,
        install_hint="npm install -g agent-browser",
    ),
    OptionalFeature(
        name="context7",
        display_name="Context7 MCP",
        description="Enhanced library documentation context",
        detection_type="binary",
        detection_target="context7",
        skill_name=None,
        plugin_key="context7@claude-plugins-official",
        install_hint="See https://context7.dev for installation",
    ),
)


def get_feature_by_name(name: str) -> OptionalFeature | None:
    """Get an optional feature definition by name.

    Args:
        name: The feature name to look up.

    Returns:
        The OptionalFeature if found, None otherwise.
    """
    for feature in OPTIONAL_FEATURES:
        if feature.name == name:
            return feature
    return None


class OptionalFeaturesService:
    """Service for detecting and managing optional feature availability.

    This service provides centralized detection of optional dependencies
    like agent-browser and context7, and helps configure ClaudeSprint
    based on what's available.

    Example:
        >>> service = OptionalFeaturesService()
        >>> detected = service.detect_all()
        >>> if detected["agent-browser"]:
        ...     print("Browser automation available!")
    """

    def __init__(self, npm_timeout: float = 5.0) -> None:
        """Initialize the service.

        Args:
            npm_timeout: Timeout in seconds for npm commands.
        """
        self._npm_timeout = npm_timeout
        self._cache: dict[str, bool] | None = None

    def detect_feature(self, name: str) -> bool:
        """Detect if a specific feature is available.

        Args:
            name: The feature name to check.

        Returns:
            True if the feature is available, False otherwise.
        """
        feature = get_feature_by_name(name)
        if feature is None:
            logger.warning("Unknown feature: %s", name)
            return False

        if feature.detection_type == "npm":
            return self._detect_npm_package(feature.detection_target)
        elif feature.detection_type == "binary":
            return self._detect_binary(feature.detection_target)
        else:
            logger.warning("Unknown detection type: %s", feature.detection_type)
            return False

    def detect_all(self) -> dict[str, bool]:
        """Detect availability of all optional features.

        Returns:
            Dictionary mapping feature names to availability status.
        """
        if self._cache is not None:
            return self._cache

        result = {}
        for feature in OPTIONAL_FEATURES:
            result[feature.name] = self.detect_feature(feature.name)

        self._cache = result
        return result

    def reload(self) -> dict[str, bool]:
        """Force re-detection of all features.

        Returns:
            Fresh detection results.
        """
        self._cache = None
        return self.detect_all()

    def get_features_summary(self) -> list[tuple[str, str, bool, str]]:
        """Get a summary of all features with their status.

        Returns:
            List of tuples: (name, display_name, available, install_hint)
        """
        detected = self.detect_all()
        result = []
        for feature in OPTIONAL_FEATURES:
            result.append((
                feature.name,
                feature.display_name,
                detected.get(feature.name, False),
                feature.install_hint,
            ))
        return result

    def get_available_features(self) -> list[OptionalFeature]:
        """Get list of available features.

        Returns:
            List of OptionalFeature objects that are available.
        """
        detected = self.detect_all()
        return [f for f in OPTIONAL_FEATURES if detected.get(f.name, False)]

    def get_unavailable_features(self) -> list[OptionalFeature]:
        """Get list of unavailable features.

        Returns:
            List of OptionalFeature objects that are not available.
        """
        detected = self.detect_all()
        return [f for f in OPTIONAL_FEATURES if not detected.get(f.name, False)]

    def get_enabled_plugins(self, detected: dict[str, bool] | None = None) -> dict[str, bool]:
        """Get enabledPlugins configuration based on available features.

        Args:
            detected: Optional pre-computed detection results.

        Returns:
            Dictionary for settings.json enabledPlugins.
        """
        if detected is None:
            detected = self.detect_all()

        plugins: dict[str, bool] = {}
        for feature in OPTIONAL_FEATURES:
            if feature.plugin_key and detected.get(feature.name, False):
                plugins[feature.plugin_key] = True
        return plugins

    def _detect_npm_package(self, package_name: str) -> bool:
        """Check if an npm package is installed globally.

        Args:
            package_name: The npm package name to check.

        Returns:
            True if the package is installed globally.
        """
        # First check if npm is available
        if shutil.which("npm") is None:
            logger.debug("npm not found, cannot detect %s", package_name)
            return False

        try:
            result = subprocess.run(
                ["npm", "list", "-g", package_name, "--depth=0"],
                capture_output=True,
                text=True,
                timeout=self._npm_timeout,
            )
            return package_name in result.stdout
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            logger.debug("Failed to detect npm package %s: %s", package_name, e)
            return False

    def _detect_binary(self, binary_name: str) -> bool:
        """Check if a binary is available in PATH.

        Args:
            binary_name: The binary name to check.

        Returns:
            True if the binary is found in PATH.
        """
        return shutil.which(binary_name) is not None
