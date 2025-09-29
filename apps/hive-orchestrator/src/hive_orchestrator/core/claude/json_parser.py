"""
Robust JSON extraction and parsing utilities
"""

import json
import re
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

from hive_logging import get_logger

logger = get_logger(__name__)


class JsonExtractionStrategy(Enum):
    """Strategies for extracting JSON from text"""

    PURE_JSON = "pure_json"
    MARKDOWN_BLOCKS = "markdown_blocks"
    REGEX_OBJECT = "regex_object"
    UNSTRUCTURED_TEXT = "unstructured_text"


class BaseExtractor(ABC):
    """Base class for JSON extraction strategies"""

    @abstractmethod
    def extract(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from text"""
        pass


class PureJsonExtractor(BaseExtractor):
    """Extract pure JSON from text"""

    def extract(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            return None


class MarkdownBlockExtractor(BaseExtractor):
    """Extract JSON from markdown code blocks"""

    PATTERNS = [r"```json\s*(.*?)\s*```", r"```\s*(.*?)\s*```", r"`(.*?)`"]

    def extract(self, text: str) -> Optional[Dict[str, Any]]:
        for pattern in self.PATTERNS:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
        return None


class RegexObjectExtractor(BaseExtractor):
    """Extract JSON objects using regex patterns"""

    JSON_PATTERN = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"

    def extract(self, text: str) -> Optional[Dict[str, Any]]:
        matches = re.findall(self.JSON_PATTERN, text, re.DOTALL)

        for match in matches:
            try:
                # Clean up common issues
                cleaned = match.replace("\n", " ").replace("\\n", " ")
                return json.loads(cleaned)
            except json.JSONDecodeError:
                continue
        return None


class JsonExtractor:
    """
    Main JSON extraction utility with multiple strategies
    """

    def __init__(self) -> None:
        self.extractors = {
            JsonExtractionStrategy.PURE_JSON: PureJsonExtractor(),
            JsonExtractionStrategy.MARKDOWN_BLOCKS: MarkdownBlockExtractor(),
            JsonExtractionStrategy.REGEX_OBJECT: RegexObjectExtractor(),
        }

    def extract_json(
        self, text: str, strategies: Optional[List[JsonExtractionStrategy]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from text using multiple strategies

        Args:
            text: Input text containing JSON
            strategies: List of strategies to try (default: all)

        Returns:
            Extracted JSON dict or None if extraction fails
        """
        if not text:
            return None

        # Default to trying all strategies in order
        if strategies is None:
            strategies = [
                JsonExtractionStrategy.PURE_JSON,
                JsonExtractionStrategy.MARKDOWN_BLOCKS,
                JsonExtractionStrategy.REGEX_OBJECT,
            ]

        for strategy in strategies:
            if strategy in self.extractors:
                result = self.extractors[strategy].extract(text)
                if result is not None:
                    logger.debug(f"Successfully extracted JSON using {strategy.value}")
                    return result

        logger.warning("All JSON extraction strategies failed")
        return None

    def extract_multiple(self, text: str, max_items: int = 10) -> List[Dict[str, Any]]:
        """
        Extract multiple JSON objects from text

        Args:
            text: Input text containing multiple JSON objects
            max_items: Maximum number of objects to extract

        Returns:
            List of extracted JSON dictionaries
        """
        results = []

        # Try to find all JSON-like structures
        json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
        matches = re.findall(json_pattern, text, re.DOTALL)

        for match in matches[:max_items]:
            try:
                cleaned = match.replace("\n", " ").replace("\\n", " ")
                data = json.loads(cleaned)
                results.append(data)
            except json.JSONDecodeError:
                continue

        return results
