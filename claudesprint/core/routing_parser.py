"""Routing signal parser for workflow step output.

Parses <routing_signal> XML tags from Claude's output to determine
workflow routing decisions. Uses xml.etree.ElementTree for robust
parsing with regex fallback for malformed content.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claudesprint.models.current_issue import IssueStep

from claudesprint.core.step_types import ParseResult


@dataclass(frozen=True)
class RoutingParserConfig:
    """Configuration for the routing signal parser.

    Attributes:
        case_sensitive: Whether signal matching is case-sensitive.
        strip_whitespace: Whether to strip whitespace from signal content.
        use_xml_fallback: Whether to try regex when XML parsing fails.
    """

    case_sensitive: bool = False
    strip_whitespace: bool = True
    use_xml_fallback: bool = True


def create_default_parser_config() -> RoutingParserConfig:
    """Create the default parser configuration."""
    return RoutingParserConfig()


class RoutingSignalParser:
    """Parser for routing_signal XML tags in step output.

    Handles various formats including:
    - Standard: <routing_signal>pass</routing_signal>
    - Whitespace: <routing_signal>  pass  </routing_signal>
    - Newlines: <routing_signal>\npass\n</routing_signal>
    - Attributes: <routing_signal type="result">pass</routing_signal>
    - Case variations: <ROUTING_SIGNAL>PASS</ROUTING_SIGNAL>
    """

    # Tag name for routing signals
    TAG_NAME = "routing_signal"

    # Regex pattern to find routing_signal tags (case-insensitive)
    _SIGNAL_PATTERN = re.compile(
        r"<routing_signal[^>]*>\s*(\w+)\s*</routing_signal>",
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(
        self,
        step_routing: dict[IssueStep, dict[str, IssueStep | None]],
        output_patterns: dict[IssueStep, dict[str, list[str]]],
        config: RoutingParserConfig | None = None,
    ) -> None:
        """Initialize the routing signal parser.

        Args:
            step_routing: Mapping of steps to routing destinations.
            output_patterns: Legacy regex patterns (kept for compatibility).
            config: Optional parser configuration.
        """
        self._step_routing = step_routing
        self._output_patterns = output_patterns
        self._config = config or create_default_parser_config()

    def parse(self, step: IssueStep, output: str) -> ParseResult:
        """Parse step output to determine next step based on signals.

        Args:
            step: Current workflow step.
            output: Claude's output text.

        Returns:
            ParseResult with next step and matched signal (if any).
        """
        routing = self._step_routing.get(step, {})
        if not routing:
            # No routing defined for this step
            return ParseResult(next_step=None, matched_signal=None)

        # Try XML parsing first
        signal = self._extract_signal_xml(output)

        # Fall back to regex if XML parsing failed
        if signal is None and self._config.use_xml_fallback:
            signal = self._extract_signal_regex(output)

        # Normalize the signal
        if signal is not None:
            signal = self._normalize_signal(signal)

            # Check if signal matches a valid route
            if signal in routing:
                return ParseResult(
                    next_step=routing[signal],
                    matched_signal=signal,
                )

        # Fall back to default routing
        return ParseResult(
            next_step=routing.get("default"),
            matched_signal=None,
        )

    def _extract_signal_xml(self, output: str) -> str | None:
        """Extract routing signal using XML parsing.

        Args:
            output: Claude's output text.

        Returns:
            Signal text if found, None otherwise.
        """
        # Find all potential routing_signal tags in the output
        # We need to be lenient since the output may contain non-XML content
        matches = list(re.finditer(
            r"<routing_signal[^>]*>.*?</routing_signal>",
            output,
            re.IGNORECASE | re.DOTALL,
        ))

        if not matches:
            return None

        # Use the last match (most recent signal)
        last_match = matches[-1]
        xml_fragment = last_match.group(0)

        try:
            # Normalize tag names for case-insensitive parsing
            xml_normalized = self._normalize_xml_tags(xml_fragment)
            root = ET.fromstring(xml_normalized)

            # Extract text content
            text = root.text
            if text is not None:
                return text

        except ET.ParseError:
            # XML parsing failed, let the caller try regex fallback
            pass

        return None

    def _normalize_xml_tags(self, xml_text: str) -> str:
        """Normalize XML tag names to lowercase for parsing.

        Args:
            xml_text: XML fragment with potentially mixed-case tags.

        Returns:
            XML fragment with lowercase tags.
        """
        # Replace opening tag with any attributes
        result = re.sub(
            r"<(routing_signal)([^>]*)>",
            r"<\1\2>",
            xml_text,
            flags=re.IGNORECASE,
        )
        # Replace opening tag
        result = re.sub(
            r"<ROUTING_SIGNAL",
            "<routing_signal",
            result,
            flags=re.IGNORECASE,
        )
        # Replace closing tag
        result = re.sub(
            r"</ROUTING_SIGNAL>",
            "</routing_signal>",
            result,
            flags=re.IGNORECASE,
        )
        return result

    def _extract_signal_regex(self, output: str) -> str | None:
        """Extract routing signal using regex fallback.

        This handles malformed XML or edge cases that the XML parser
        can't handle.

        Args:
            output: Claude's output text.

        Returns:
            Signal text if found, None otherwise.
        """
        matches = list(self._SIGNAL_PATTERN.finditer(output))
        if matches:
            # Use the last match (most recent signal)
            return matches[-1].group(1)
        return None

    def _normalize_signal(self, signal: str) -> str:
        """Normalize a signal value for matching.

        Args:
            signal: Raw signal text.

        Returns:
            Normalized signal for comparison.
        """
        if self._config.strip_whitespace:
            signal = signal.strip()

        if not self._config.case_sensitive:
            signal = signal.lower()

        return signal
