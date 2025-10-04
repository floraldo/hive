"""Parse natural language feature descriptions into test scenarios."""

from __future__ import annotations

import re

from hive_logging import get_logger

from .models import AssertionType, TestScenario, UserAction

logger = get_logger(__name__)


class ScenarioParser:
    """
    Parse feature descriptions into structured test scenarios.

    Extracts user actions, assertions, and page elements from natural
    language descriptions to generate test code.

    Example:
        parser = ScenarioParser()
        scenario = parser.parse(
            feature="User can login with Google OAuth",
            url="https://myapp.dev/login"
        )
    """

    # Action patterns
    ACTION_PATTERNS = {
        UserAction.NAVIGATE: [
            r"(?:navigate|go|visit) (?:to )?(.+)",
            r"open (.+)",
            r"load (.+) page",
        ],
        UserAction.CLICK: [
            r"click (?:on )?(?:the )?(.+?) button",
            r"press (?:the )?(.+?) button",
            r"select (.+?) option",
        ],
        UserAction.FILL: [
            r"(?:enter|type|fill|input) (.+?) (?:in|into) (?:the )?(.+?) field",
            r"(?:fill|complete) (?:the )?(.+?) (?:field|input) with (.+?)",
        ],
        UserAction.VERIFY: [
            r"(?:verify|check|ensure) (?:that )?(.+?) is (?:visible|displayed|shown)",
            r"(?:should see|see) (?:the )?(.+?)",
            r"(?:confirm|validate) (.+?) (?:appears|exists)",
        ],
    }

    # Element selectors (heuristic mapping)
    ELEMENT_SELECTORS = {
        "login button": "button[data-testid='login']",
        "google button": "button[data-testid='google-login']",
        "email field": "input[name='email']",
        "password field": "input[name='password']",
        "submit button": "button[type='submit']",
        "error message": ".error-message",
        "success message": ".success-message",
        "dashboard": "#dashboard",
        "user menu": "[data-testid='user-menu']",
    }

    def __init__(self) -> None:
        """Initialize scenario parser."""
        self.logger = logger

    def parse(
        self,
        feature: str,
        url: str,
        additional_context: dict[str, str] | None = None
    ) -> TestScenario:
        """
        Parse feature description into structured test scenario.

        Args:
            feature: Natural language feature description
            url: Target URL for testing
            additional_context: Optional context hints

        Returns:
            Structured test scenario with actions and assertions

        Example:
            scenario = parser.parse(
                feature="User can login with Google OAuth",
                url="https://myapp.dev/login",
                additional_context={
                    "success_indicator": "User dashboard visible",
                    "failure_indicator": "Error message displayed"
                }
            )
        """
        self.logger.info(f"Parsing feature: {feature}")

        # Extract feature name
        feature_name = self._extract_feature_name(feature)

        # Parse user actions
        actions = self._extract_actions(feature)

        # Generate success assertions
        success_assertions = self._generate_success_assertions(
            feature,
            additional_context
        )

        # Generate failure assertions
        failure_assertions = self._generate_failure_assertions(
            feature,
            additional_context
        )

        # Extract page elements
        page_elements = self._extract_page_elements(feature, actions)

        scenario = TestScenario(
            feature_name=feature_name,
            description=feature,
            target_url=url,
            actions=actions,
            success_assertions=success_assertions,
            failure_assertions=failure_assertions,
            page_elements=page_elements,
        )

        self.logger.info(
            f"Parsed scenario: {len(actions)} actions, "
            f"{len(success_assertions)} success assertions, "
            f"{len(page_elements)} elements"
        )

        return scenario

    def _extract_feature_name(self, feature: str) -> str:
        """Extract concise feature name from description."""
        # Remove common prefixes
        name = re.sub(r"^(?:User can |Users can |Can |Should |Must )", "", feature)

        # Truncate at first sentence/clause
        name = re.split(r"[.;,]", name)[0].strip()

        # Convert to title case
        return name.title()

    def _extract_actions(self, feature: str) -> list[dict[str, str]]:
        """Extract user actions from feature description."""
        actions = []

        # Lowercase for pattern matching
        feature_lower = feature.lower()

        for action_type, patterns in self.ACTION_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, feature_lower)
                for match in matches:
                    if isinstance(match, tuple):
                        # Multiple capture groups
                        actions.append({
                            "type": action_type.value,
                            "target": match[0] if match else "",
                            "value": match[1] if len(match) > 1 else "",
                        })
                    else:
                        # Single capture group
                        actions.append({
                            "type": action_type.value,
                            "target": match,
                            "value": "",
                        })

        return actions

    def _generate_success_assertions(
        self,
        feature: str,
        context: dict[str, str] | None
    ) -> list[dict[str, str]]:
        """Generate assertions for successful scenario."""
        assertions = []

        # Use context hints if provided
        if context and "success_indicator" in context:
            assertions.append({
                "type": AssertionType.VISIBLE.value,
                "target": context["success_indicator"],
                "message": f"{context['success_indicator']} should be visible",
            })

        # Infer from feature description
        feature_lower = feature.lower()

        # Dashboard visibility (common success indicator)
        if "login" in feature_lower or "sign in" in feature_lower:
            assertions.append({
                "type": AssertionType.VISIBLE.value,
                "target": "user dashboard",
                "message": "User should be redirected to dashboard",
            })

        # URL change
        if "redirect" in feature_lower or "navigate" in feature_lower:
            assertions.append({
                "type": AssertionType.URL_MATCHES.value,
                "target": "success_url_pattern",
                "message": "URL should change after success",
            })

        # Default: verify action completed
        if not assertions:
            assertions.append({
                "type": AssertionType.ELEMENT_EXISTS.value,
                "target": "success indicator",
                "message": "Action should complete successfully",
            })

        return assertions

    def _generate_failure_assertions(
        self,
        feature: str,
        context: dict[str, str] | None
    ) -> list[dict[str, str]]:
        """Generate assertions for failure scenario."""
        assertions = []

        # Use context hints if provided
        if context and "failure_indicator" in context:
            assertions.append({
                "type": AssertionType.VISIBLE.value,
                "target": context["failure_indicator"],
                "message": f"{context['failure_indicator']} should be visible on failure",
            })

        # Default: error message visible
        if not assertions:
            assertions.append({
                "type": AssertionType.VISIBLE.value,
                "target": "error message",
                "message": "Error message should be displayed on failure",
            })

        return assertions

    def _extract_page_elements(
        self,
        feature: str,
        actions: list[dict[str, str]]
    ) -> dict[str, str]:
        """Extract page elements and map to selectors."""
        elements = {}

        feature_lower = feature.lower()

        # Extract from actions
        for action in actions:
            target = action.get("target", "").lower()

            # Match against known selectors
            for element_name, selector in self.ELEMENT_SELECTORS.items():
                if element_name in target or element_name in feature_lower:
                    elements[element_name] = selector

        # Add common elements based on feature type
        if "login" in feature_lower or "sign in" in feature_lower:
            elements.setdefault("email field", "input[name='email']")
            elements.setdefault("password field", "input[name='password']")
            elements.setdefault("login button", "button[type='submit']")

        return elements
