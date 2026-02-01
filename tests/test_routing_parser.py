"""Tests for RoutingSignalParser."""


import pytest

from claudesprint.core.routing_parser import (
    RoutingParserConfig,
    RoutingSignalParser,
    create_default_parser_config,
)
from claudesprint.models.current_issue import IssueStep


@pytest.fixture
def step_routing() -> dict[IssueStep, dict[str, IssueStep | None]]:
    """Sample step routing table for testing."""
    return {
        IssueStep.RUN_TESTS: {
            "pass": IssueStep.BROWSER_VALIDATION,
            "fail_code": IssueStep.IMPLEMENT,
            "fail_test": IssueStep.FIX_TESTS,
            "default": IssueStep.BROWSER_VALIDATION,
        },
        IssueStep.BROWSER_VALIDATION: {
            "pass": IssueStep.CODE_REVIEW,
            "fail": IssueStep.IMPLEMENT,
            "skip": IssueStep.CODE_REVIEW,
            "default": IssueStep.CODE_REVIEW,
        },
        IssueStep.CODE_REVIEW: {
            "pass": IssueStep.UPDATE_DOCS,
            "issues": IssueStep.FIX_CODE_REVIEW_ISSUES,
            "default": IssueStep.UPDATE_DOCS,
        },
    }


@pytest.fixture
def output_patterns() -> dict[IssueStep, dict[str, list[str]]]:
    """Legacy output patterns (empty for new parser)."""
    return {}


@pytest.fixture
def parser(
    step_routing: dict[IssueStep, dict[str, IssueStep | None]],
    output_patterns: dict[IssueStep, dict[str, list[str]]],
) -> RoutingSignalParser:
    """Create a parser with default config."""
    return RoutingSignalParser(step_routing, output_patterns)


class TestRoutingSignalParserBasic:
    """Basic parsing tests."""

    def test_parse_simple_pass_signal(self, parser: RoutingSignalParser) -> None:
        """Parser correctly identifies a simple pass signal."""
        output = "Tests completed.\n<routing_signal>pass</routing_signal>"
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "pass"
        assert result.next_step == IssueStep.BROWSER_VALIDATION

    def test_parse_simple_fail_code_signal(self, parser: RoutingSignalParser) -> None:
        """Parser correctly identifies a fail_code signal."""
        output = "Tests failed due to code error.\n<routing_signal>fail_code</routing_signal>"
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "fail_code"
        assert result.next_step == IssueStep.IMPLEMENT

    def test_parse_fail_test_signal(self, parser: RoutingSignalParser) -> None:
        """Parser correctly identifies a fail_test signal."""
        output = "Test assertions failed.\n<routing_signal>fail_test</routing_signal>"
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "fail_test"
        assert result.next_step == IssueStep.FIX_TESTS

    def test_default_routing_when_no_signal(self, parser: RoutingSignalParser) -> None:
        """Parser falls back to default routing when no signal found."""
        output = "Some output without a signal."
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal is None
        assert result.next_step == IssueStep.BROWSER_VALIDATION

    def test_no_routing_for_unknown_step(self, parser: RoutingSignalParser) -> None:
        """Parser returns None when step has no routing defined."""
        output = "<routing_signal>pass</routing_signal>"
        result = parser.parse(IssueStep.IMPLEMENT, output)

        assert result.matched_signal is None
        assert result.next_step is None


class TestRoutingSignalParserWhitespace:
    """Tests for whitespace handling."""

    def test_parse_signal_with_leading_whitespace(self, parser: RoutingSignalParser) -> None:
        """Parser handles leading whitespace inside tag."""
        output = "<routing_signal>  pass</routing_signal>"
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "pass"
        assert result.next_step == IssueStep.BROWSER_VALIDATION

    def test_parse_signal_with_trailing_whitespace(self, parser: RoutingSignalParser) -> None:
        """Parser handles trailing whitespace inside tag."""
        output = "<routing_signal>pass  </routing_signal>"
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "pass"
        assert result.next_step == IssueStep.BROWSER_VALIDATION

    def test_parse_signal_with_both_whitespace(self, parser: RoutingSignalParser) -> None:
        """Parser handles whitespace on both sides."""
        output = "<routing_signal>  pass  </routing_signal>"
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "pass"
        assert result.next_step == IssueStep.BROWSER_VALIDATION


class TestRoutingSignalParserNewlines:
    """Tests for newline handling."""

    def test_parse_signal_with_newlines(self, parser: RoutingSignalParser) -> None:
        """Parser handles newlines inside tag."""
        output = "<routing_signal>\npass\n</routing_signal>"
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "pass"
        assert result.next_step == IssueStep.BROWSER_VALIDATION

    def test_parse_signal_with_mixed_whitespace(self, parser: RoutingSignalParser) -> None:
        """Parser handles mixed whitespace and newlines."""
        output = "<routing_signal>\n  pass  \n</routing_signal>"
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "pass"
        assert result.next_step == IssueStep.BROWSER_VALIDATION

    def test_parse_signal_with_crlf(self, parser: RoutingSignalParser) -> None:
        """Parser handles Windows-style line endings."""
        output = "<routing_signal>\r\npass\r\n</routing_signal>"
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "pass"
        assert result.next_step == IssueStep.BROWSER_VALIDATION


class TestRoutingSignalParserAttributes:
    """Tests for XML attribute handling."""

    def test_parse_signal_with_type_attribute(self, parser: RoutingSignalParser) -> None:
        """Parser handles routing_signal tag with type attribute."""
        output = '<routing_signal type="result">pass</routing_signal>'
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "pass"
        assert result.next_step == IssueStep.BROWSER_VALIDATION

    def test_parse_signal_with_multiple_attributes(self, parser: RoutingSignalParser) -> None:
        """Parser handles routing_signal tag with multiple attributes."""
        output = '<routing_signal type="result" confidence="high">pass</routing_signal>'
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "pass"
        assert result.next_step == IssueStep.BROWSER_VALIDATION

    def test_parse_signal_with_attribute_and_whitespace(self, parser: RoutingSignalParser) -> None:
        """Parser handles attributes combined with internal whitespace."""
        output = '<routing_signal type="result">  pass  </routing_signal>'
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "pass"
        assert result.next_step == IssueStep.BROWSER_VALIDATION


class TestRoutingSignalParserCase:
    """Tests for case sensitivity handling."""

    def test_parse_uppercase_tag(self, parser: RoutingSignalParser) -> None:
        """Parser handles uppercase tag name."""
        output = "<ROUTING_SIGNAL>pass</ROUTING_SIGNAL>"
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "pass"
        assert result.next_step == IssueStep.BROWSER_VALIDATION

    def test_parse_mixed_case_tag(self, parser: RoutingSignalParser) -> None:
        """Parser handles mixed case tag name."""
        output = "<Routing_Signal>pass</Routing_Signal>"
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "pass"
        assert result.next_step == IssueStep.BROWSER_VALIDATION

    def test_parse_uppercase_signal_content(self, parser: RoutingSignalParser) -> None:
        """Parser handles uppercase signal content."""
        output = "<routing_signal>PASS</routing_signal>"
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "pass"
        assert result.next_step == IssueStep.BROWSER_VALIDATION

    def test_parse_uppercase_tag_and_content(self, parser: RoutingSignalParser) -> None:
        """Parser handles all uppercase tag and content."""
        output = "<ROUTING_SIGNAL>PASS</ROUTING_SIGNAL>"
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "pass"
        assert result.next_step == IssueStep.BROWSER_VALIDATION


class TestRoutingSignalParserEdgeCases:
    """Tests for edge cases."""

    def test_parse_empty_output(self, parser: RoutingSignalParser) -> None:
        """Parser handles empty output."""
        result = parser.parse(IssueStep.RUN_TESTS, "")

        assert result.matched_signal is None
        assert result.next_step == IssueStep.BROWSER_VALIDATION  # default

    def test_parse_multiple_signals_uses_last(self, parser: RoutingSignalParser) -> None:
        """Parser uses the last signal when multiple are present."""
        output = (
            "<routing_signal>fail_code</routing_signal>\n"
            "More output...\n"
            "<routing_signal>pass</routing_signal>"
        )
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "pass"
        assert result.next_step == IssueStep.BROWSER_VALIDATION

    def test_parse_signal_embedded_in_text(self, parser: RoutingSignalParser) -> None:
        """Parser finds signal embedded in other text."""
        output = (
            "I ran the tests and they all passed.\n"
            "Here is the summary:\n"
            "- 10 tests passed\n"
            "- 0 tests failed\n"
            "\n"
            "<routing_signal>pass</routing_signal>\n"
            "\n"
            "That's all!"
        )
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "pass"
        assert result.next_step == IssueStep.BROWSER_VALIDATION

    def test_parse_invalid_signal_uses_default(self, parser: RoutingSignalParser) -> None:
        """Parser uses default when signal doesn't match valid options."""
        output = "<routing_signal>unknown_signal</routing_signal>"
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal is None
        assert result.next_step == IssueStep.BROWSER_VALIDATION  # default

    def test_parse_signal_with_underscore(self, parser: RoutingSignalParser) -> None:
        """Parser handles signals with underscores."""
        output = "<routing_signal>fail_code</routing_signal>"
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "fail_code"
        assert result.next_step == IssueStep.IMPLEMENT


class TestRoutingSignalParserConfig:
    """Tests for parser configuration."""

    def test_default_config_values(self) -> None:
        """Default config has expected values."""
        config = create_default_parser_config()

        assert config.case_sensitive is False
        assert config.strip_whitespace is True
        assert config.use_xml_fallback is True

    def test_case_sensitive_config(
        self,
        step_routing: dict[IssueStep, dict[str, IssueStep | None]],
        output_patterns: dict[IssueStep, dict[str, list[str]]],
    ) -> None:
        """Parser respects case_sensitive config."""
        config = RoutingParserConfig(case_sensitive=True)
        parser = RoutingSignalParser(step_routing, output_patterns, config)

        # PASS should not match "pass" when case-sensitive
        output = "<routing_signal>PASS</routing_signal>"
        result = parser.parse(IssueStep.RUN_TESTS, output)

        # Falls back to default because "PASS" doesn't match "pass"
        assert result.matched_signal is None
        assert result.next_step == IssueStep.BROWSER_VALIDATION

    def test_disable_xml_fallback(
        self,
        step_routing: dict[IssueStep, dict[str, IssueStep | None]],
        output_patterns: dict[IssueStep, dict[str, list[str]]],
    ) -> None:
        """Parser respects use_xml_fallback config."""
        config = RoutingParserConfig(use_xml_fallback=False)
        parser = RoutingSignalParser(step_routing, output_patterns, config)

        # This should still work with XML parsing
        output = "<routing_signal>pass</routing_signal>"
        result = parser.parse(IssueStep.RUN_TESTS, output)

        assert result.matched_signal == "pass"


class TestRoutingSignalParserDifferentSteps:
    """Tests for different step types."""

    def test_browser_validation_pass(self, parser: RoutingSignalParser) -> None:
        """Parser handles browser validation pass."""
        output = "<routing_signal>pass</routing_signal>"
        result = parser.parse(IssueStep.BROWSER_VALIDATION, output)

        assert result.matched_signal == "pass"
        assert result.next_step == IssueStep.CODE_REVIEW

    def test_browser_validation_fail(self, parser: RoutingSignalParser) -> None:
        """Parser handles browser validation fail."""
        output = "<routing_signal>fail</routing_signal>"
        result = parser.parse(IssueStep.BROWSER_VALIDATION, output)

        assert result.matched_signal == "fail"
        assert result.next_step == IssueStep.IMPLEMENT

    def test_browser_validation_skip(self, parser: RoutingSignalParser) -> None:
        """Parser handles browser validation skip."""
        output = "<routing_signal>skip</routing_signal>"
        result = parser.parse(IssueStep.BROWSER_VALIDATION, output)

        assert result.matched_signal == "skip"
        assert result.next_step == IssueStep.CODE_REVIEW

    def test_code_review_pass(self, parser: RoutingSignalParser) -> None:
        """Parser handles code review pass."""
        output = "<routing_signal>pass</routing_signal>"
        result = parser.parse(IssueStep.CODE_REVIEW, output)

        assert result.matched_signal == "pass"
        assert result.next_step == IssueStep.UPDATE_DOCS

    def test_code_review_issues(self, parser: RoutingSignalParser) -> None:
        """Parser handles code review issues."""
        output = "<routing_signal>issues</routing_signal>"
        result = parser.parse(IssueStep.CODE_REVIEW, output)

        assert result.matched_signal == "issues"
        assert result.next_step == IssueStep.FIX_CODE_REVIEW_ISSUES
