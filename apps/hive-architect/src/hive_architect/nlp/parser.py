"""Natural Language Requirement Parser.

Extracts structured information from natural language service descriptions.
Uses pattern matching and keyword detection for MVP implementation.
"""

from __future__ import annotations

import re

from hive_logging import get_logger

from ..models import ParsedRequirement, ServiceType

logger = get_logger(__name__)


class RequirementParser:
    """Parse natural language requirements into structured format.

    Example:
        parser = RequirementParser()
        requirement = parser.parse("Create a 'feedback-service' API that stores user feedback")
        # Returns ParsedRequirement with extracted structure

    """

    # Service type detection patterns
    API_PATTERNS = [
        r"\bapi\b",
        r"\brest\b",
        r"\bendpoint",
        r"\broute",
        r"\bhttp\b",
        r"\bweb service\b",
    ]

    WORKER_PATTERNS = [
        r"\bworker\b",
        r"\bevent",
        r"\bmessage queue\b",
        r"\bprocess.*queue",
        r"\basync.*process",
    ]

    BATCH_PATTERNS = [
        r"\bbatch\b",
        r"\bscheduled",
        r"\bcron",
        r"\bjob",
        r"\bperiodic",
    ]

    # Feature detection patterns
    DATABASE_PATTERNS = [
        r"\bstore",
        r"\bsave",
        r"\bdatabase\b",
        r"\bpersist",
        r"\brecord",
    ]

    CACHING_PATTERNS = [
        r"\bcache",
        r"\bfast lookup",
        r"\bin-memory",
    ]

    ASYNC_PATTERNS = [
        r"\basync",
        r"\bconcurrent",
        r"\bparallel",
        r"\bnon-blocking",
    ]

    # Python built-in modules and reserved names to avoid
    PYTHON_BUILTINS = {
        "uuid",
        "json",
        "time",
        "logging",
        "config",
        "path",
        "sys",
        "os",
        "io",
        "re",
        "test",
        "main",
        "http",
        "email",
        "string",
        "data",
        "file",
        "user",
    }

    def __init__(self) -> None:
        """Initialize the parser"""
        self.logger = logger

    def parse(self, requirement_text: str) -> ParsedRequirement:
        """Parse natural language requirement into structured format.

        Args:
            requirement_text: Natural language description

        Returns:
            ParsedRequirement with extracted information

        """
        self.logger.info(f"Parsing requirement: {requirement_text[:100]}...")

        # Extract service name (from quotes or hyphens)
        service_name = self._extract_service_name(requirement_text)

        # Detect service type
        service_type = self._detect_service_type(requirement_text)

        # Extract features
        features = self._extract_features(requirement_text)

        # Detect capabilities
        enable_database = self._matches_patterns(
            requirement_text,
            self.DATABASE_PATTERNS,
        )
        enable_caching = self._matches_patterns(
            requirement_text,
            self.CACHING_PATTERNS,
        )
        enable_async = self._matches_patterns(requirement_text, self.ASYNC_PATTERNS)

        # Extract constraints and rules
        technical_constraints = self._extract_technical_constraints(requirement_text)
        business_rules = self._extract_business_rules(requirement_text)

        # Calculate confidence
        confidence_score = self._calculate_confidence(
            service_name,
            service_type,
            features,
        )

        parsed = ParsedRequirement(
            service_name=service_name,
            service_type=service_type,
            features=features,
            enable_database=enable_database,
            enable_caching=enable_caching,
            enable_async=enable_async,
            technical_constraints=technical_constraints,
            business_rules=business_rules,
            confidence_score=confidence_score,
        )

        self.logger.info(
            f"Parsed requirement: {parsed.service_name} ({parsed.service_type}) "
            f"with {len(parsed.features)} features (confidence: {confidence_score:.2f})",
        )

        return parsed

    def _extract_service_name(self, text: str) -> str:
        """Extract service name from text with context-aware validation.

        Prioritizes explicit service names over JSON field values and
        validates against Python built-ins to prevent conflicts.

        Args:
            text: Natural language requirement text

        Returns:
            Validated service name (safe for Python modules)
        """
        # Split text to separate natural language from JSON/examples
        # This prevents extracting field names from JSON structures
        parts = re.split(
            r'(?:\n\s*\{|\bExpected\s+(?:JSON|structure|format|output)\b|\bExample\b)',
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )
        natural_text = parts[0] if parts else text

        # Try quoted names first (highest priority) - search natural text only
        quoted_matches = re.findall(
            r"['\"]([a-z0-9-]+)['\"]", natural_text, re.IGNORECASE
        )

        # Filter out Python built-ins
        for name in quoted_matches:
            if name.lower() in self.PYTHON_BUILTINS:
                self.logger.warning(
                    f"Skipping '{name}': conflicts with Python built-in module"
                )
                continue
            # Valid service name found
            self.logger.info(f"Extracted service name: '{name}'")
            return name

        # Try hyphenated names (but validate)
        hyphen_match = re.search(r"\b([a-z]+-[a-z-]+)\b", natural_text, re.IGNORECASE)
        if hyphen_match:
            name = hyphen_match.group(1)
            if name.lower() not in self.PYTHON_BUILTINS:
                self.logger.info(f"Extracted hyphenated name: '{name}'")
                return name
            self.logger.warning(
                f"Skipping hyphenated name '{name}': conflicts with Python built-in"
            )

        # Default to generic name (always safe)
        self.logger.info("No explicit service name found, using default")
        return "new-service"

    def _detect_service_type(self, text: str) -> ServiceType:
        """Detect service type from text patterns"""
        text_lower = text.lower()

        if self._matches_patterns(text_lower, self.API_PATTERNS):
            return ServiceType.API
        if self._matches_patterns(text_lower, self.WORKER_PATTERNS):
            return ServiceType.WORKER
        if self._matches_patterns(text_lower, self.BATCH_PATTERNS):
            return ServiceType.BATCH

        return ServiceType.UNKNOWN

    def _extract_features(self, text: str) -> list[str]:
        """Extract feature descriptions from text"""
        features = []

        # Split by common delimiters
        sentences = re.split(r"[.;,]|\bthat\b|\band\b", text)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Look for action verbs
            if any(
                verb in sentence.lower()
                for verb in [
                    "store",
                    "save",
                    "create",
                    "process",
                    "handle",
                    "manage",
                    "track",
                ]
            ):
                features.append(sentence)

        return features[:5]  # Limit to top 5 features

    def _extract_technical_constraints(self, text: str) -> list[str]:
        """Extract technical requirements"""
        constraints = []

        # Look for performance requirements
        if re.search(r"\bfast\b|\bquick\b|\breal-time\b", text, re.IGNORECASE):
            constraints.append("Low latency required")

        # Look for scale requirements
        if re.search(r"\bscale\b|\bhigh volume\b|\bmany users\b", text, re.IGNORECASE):
            constraints.append("High scalability required")

        return constraints

    def _extract_business_rules(self, text: str) -> list[str]:
        """Extract business logic rules"""
        rules = []

        # Look for validation requirements
        if re.search(r"\bvalidate\b|\bcheck\b|\bverify\b", text, re.IGNORECASE):
            rules.append("Input validation required")

        # Look for auth requirements
        if re.search(r"\bauth\b|\bsecure\b|\bprivate\b", text, re.IGNORECASE):
            rules.append("Authentication required")

        return rules

    def _matches_patterns(self, text: str, patterns: list[str]) -> bool:
        """Check if text matches any pattern in list"""
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)

    def _calculate_confidence(
        self,
        service_name: str,
        service_type: ServiceType,
        features: list[str],
    ) -> float:
        """Calculate confidence score for parsing"""
        confidence = 0.0

        # Service name found
        if service_name != "new-service":
            confidence += 0.4

        # Service type detected
        if service_type != ServiceType.UNKNOWN:
            confidence += 0.3

        # Features extracted
        if features:
            confidence += 0.3

        return min(confidence, 1.0)
