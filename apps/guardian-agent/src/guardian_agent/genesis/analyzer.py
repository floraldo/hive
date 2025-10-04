"""Semantic Analyzer - AI-Powered App Description Analysis

Analyzes natural language app descriptions to extract features,
dependencies, and architectural requirements.
"""

from __future__ import annotations

import re
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


class SemanticAnalyzer:
    """AI-powered semantic analysis of application descriptions.

    Extracts features, dependencies, and architectural requirements
    from natural language descriptions.
    """

    def __init__(self, config):
        self.config = config
        self.feature_patterns = self._load_feature_patterns()
        self.keyword_mappings = self._load_keyword_mappings()

    def _load_feature_patterns(self) -> dict[str, list[str]]:
        """Load patterns for identifying common features."""
        return {
            "authentication": [
                r"\b(?:login|signin|auth|user account|registration|signup)\b",
                r"\b(?:password|credential|token)\b",
            ],
            "data_storage": [r"\b(?:store|save|persist|database|data)\b", r"\b(?:record|entry|item|document)\b"],
            "file_upload": [r"\b(?:upload|file|photo|image|document|attachment)\b", r"\b(?:media|picture|video)\b"],
            "search": [r"\b(?:search|find|query|filter|lookup)\b", r"\b(?:browse|discover)\b"],
            "social_features": [r"\b(?:share|comment|like|follow|social)\b", r"\b(?:community|forum|discussion)\b"],
            "real_time": [r"\b(?:real-time|realtime|live|instant)\b", r"\b(?:notification|alert|update)\b"],
            "ai_features": [
                r"\b(?:ai|artificial intelligence|machine learning|ml|smart|intelligent)\b",
                r"\b(?:auto|automatic|suggest|recommend|analyze)\b",
                r"\b(?:tag|categorize|classify|detect)\b",
            ],
            "analytics": [r"\b(?:analytics|metrics|stats|report|dashboard)\b", r"\b(?:track|monitor|measure)\b"],
            "api": [r"\b(?:api|endpoint|service|rest|graphql)\b", r"\b(?:integration|webhook)\b"],
            "web_interface": [r"\b(?:web|website|frontend|ui|interface|dashboard)\b", r"\b(?:page|view|form|button)\b"],
        }

    def _load_keyword_mappings(self) -> dict[str, list[str]]:
        """Load mappings from keywords to hive packages."""
        return {
            "hive-db": ["data", "store", "save", "database", "user", "record", "persist", "query", "table", "model"],
            "hive-ai": [
                "ai",
                "ml",
                "intelligent",
                "smart",
                "analyze",
                "tag",
                "classify",
                "detect",
                "recommend",
                "suggest",
                "auto",
            ],
            "hive-bus": [
                "real-time",
                "message",
                "event",
                "notify",
                "update",
                "live",
                "instant",
                "notification",
                "alert",
                "stream",
            ],
            "hive-deployment": [
                "deploy",
                "production",
                "server",
                "cloud",
                "scale",
                "container",
                "kubernetes",
                "docker",
            ],
        }

    async def analyze_description_async(self, description: str) -> dict[str, Any]:
        """Analyze an application description and extract structured information.

        Args:
            description: Natural language description of the application

        Returns:
            Dict containing extracted features, keywords, and recommendations

        """
        logger.info(f"Analyzing description: {description[:100]}...")

        try:
            # Extract features using pattern matching
            features = self._extract_features(description)

            # Extract keywords and technical indicators
            keywords = self._extract_keywords(description)

            # Identify business context
            business_keywords = self._extract_business_keywords(description)

            # Suggest packages based on analysis
            suggested_packages = self._suggest_packages(features, keywords)

            # Determine app complexity
            complexity = self._assess_complexity(features, keywords)

            # Extract user personas
            user_personas = self._extract_user_personas(description)

            # Identify data requirements
            data_requirements = self._analyze_data_requirements(description, features)

            analysis_result = {
                "features": features,
                "keywords": keywords,
                "business_keywords": business_keywords,
                "suggested_packages": suggested_packages,
                "complexity": complexity,
                "user_personas": user_personas,
                "data_requirements": data_requirements,
                "confidence_score": self._calculate_confidence(features, keywords),
            }

            logger.info(f"Analysis complete - {len(features)} features identified")
            return analysis_result

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return {
                "features": [],
                "keywords": [],
                "business_keywords": [],
                "suggested_packages": ["hive-config"],
                "complexity": "medium",
                "user_personas": [],
                "data_requirements": {},
                "confidence_score": 0.0,
            }

    def _extract_features(self, description: str) -> list[str]:
        """Extract features from description using pattern matching."""
        features = ([],)
        description_lower = description.lower()

        for feature_name, patterns in self.feature_patterns.items():
            for pattern in patterns:
                if re.search(pattern, description_lower, re.IGNORECASE):
                    # Convert feature name to human-readable format
                    readable_name = feature_name.replace("_", " ").title()
                    if readable_name not in features:
                        features.append(readable_name)
                    break

        # Extract explicit feature mentions
        explicit_features = self._extract_explicit_features(description)
        features.extend(explicit_features)

        return list(set(features))  # Remove duplicates

    def _extract_explicit_features(self, description: str) -> list[str]:
        """Extract explicitly mentioned features."""
        explicit_features = []

        # Look for "feature" or "functionality" mentions
        feature_patterns = [
            r"(?:feature|functionality|capability|ability)\s+(?:to\s+)?([^.]+)",
            r"(?:can|will|should)\s+([^.]+)",
            r"(?:users?\s+can|allow\s+users?\s+to)\s+([^.]+)",
        ]

        for pattern in feature_patterns:
            matches = re.findall(pattern, description, re.IGNORECASE)
            for match in matches:
                # Clean up the match
                feature = match.strip().lower()
                if len(feature) > 3 and len(feature) < 50:  # Reasonable feature length
                    explicit_features.append(feature.title())

        return explicit_features[:5]  # Limit to top 5 explicit features

    def _extract_keywords(self, description: str) -> list[str]:
        """Extract technical keywords from description."""
        keywords = ([],)
        description_lower = description.lower()

        # Technical keywords
        tech_keywords = [
            "web",
            "api",
            "database",
            "frontend",
            "backend",
            "service",
            "real-time",
            "analytics",
            "dashboard",
            "mobile",
            "desktop",
            "cloud",
            "ai",
            "ml",
            "data",
            "user",
            "admin",
            "auth",
            "search",
            "upload",
            "download",
            "integration",
            "webhook",
        ]

        for keyword in tech_keywords:
            if keyword in description_lower:
                keywords.append(keyword)

        return keywords

    def _extract_business_keywords(self, description: str) -> list[str]:
        """Extract business context keywords."""
        business_keywords = ([],)
        description_lower = description.lower()

        # Business context keywords
        business_terms = [
            "customer",
            "user",
            "client",
            "business",
            "company",
            "team",
            "organization",
            "enterprise",
            "startup",
            "product",
            "service",
            "market",
            "revenue",
            "profit",
            "cost",
            "efficiency",
            "productivity",
            "growth",
            "scale",
            "competitive",
            "advantage",
            "value",
            "roi",
        ]

        for term in business_terms:
            if term in description_lower:
                business_keywords.append(term)

        return business_keywords

    def _suggest_packages(self, features: list[str], keywords: list[str]) -> list[str]:
        """Suggest hive packages based on identified features and keywords."""
        suggested = {"hive-config"}  # Always include base config,
        all_terms = [f.lower() for f in features] + [k.lower() for k in keywords]

        for package, package_keywords in self.keyword_mappings.items():
            for term in all_terms:
                if any(pkg_kw in term for pkg_kw in package_keywords):
                    suggested.add(package)
                    break

        return list(suggested)

    def _assess_complexity(self, features: list[str], keywords: list[str]) -> str:
        """Assess the complexity of the application."""
        complexity_indicators = {
            "high": ["ai", "ml", "real-time", "analytics", "integration", "scale"],
            "medium": ["auth", "database", "api", "search", "upload"],
            "low": ["simple", "basic", "static", "display"],
        }

        all_terms = ([f.lower() for f in features] + [k.lower() for k in keywords],)

        high_count = sum(
            1 for term in all_terms if any(indicator in term for indicator in complexity_indicators["high"])
        )
        medium_count = sum(
            1 for term in all_terms if any(indicator in term for indicator in complexity_indicators["medium"])
        )

        if high_count >= 2:
            return "high"
        if high_count >= 1 or medium_count >= 3:
            return "medium"
        return "low"

    def _extract_user_personas(self, description: str) -> list[str]:
        """Extract user personas from description."""
        personas = ([],)
        description_lower = description.lower()

        # Common user personas
        persona_patterns = [
            r"\b(admin|administrator|manager|supervisor)\b",
            r"\b(user|customer|client|member|visitor)\b",
            r"\b(developer|engineer|programmer)\b",
            r"\b(analyst|reporter|viewer)\b",
            r"\b(owner|creator|author|contributor)\b",
        ]

        for pattern in persona_patterns:
            matches = re.findall(pattern, description_lower)
            for match in matches:
                persona = match.capitalize()
                if persona not in personas:
                    personas.append(persona)

        return personas[:4]  # Limit to 4 personas

    def _analyze_data_requirements(self, description: str, features: list[str]) -> dict[str, Any]:
        """Analyze data storage and processing requirements."""
        requirements = {
            "storage_type": "sqlite",  # Default,
            "data_volume": "low",
            "data_types": [],
            "relationships": False,
        }

        description_lower = description.lower()

        # Determine storage type
        if any(term in description_lower for term in ["large", "scale", "enterprise", "millions"]):
            requirements["storage_type"] = "postgresql"
            requirements["data_volume"] = "high"
        elif any(term in description_lower for term in ["medium", "thousands", "business"]):
            requirements["storage_type"] = "postgresql"
            requirements["data_volume"] = "medium"

        # Identify data types
        data_type_patterns = {
            "text": ["text", "string", "description", "comment", "message"],
            "numeric": ["number", "count", "price", "amount", "quantity"],
            "datetime": ["date", "time", "timestamp", "schedule", "event"],
            "file": ["file", "image", "photo", "document", "media"],
            "json": ["json", "metadata", "properties", "attributes"],
        }

        for data_type, keywords in data_type_patterns.items():
            if any(keyword in description_lower for keyword in keywords):
                requirements["data_types"].append(data_type)

        # Check for relationships
        relationship_indicators = ["user", "owner", "belongs", "has many", "related", "linked"]
        if any(indicator in description_lower for indicator in relationship_indicators):
            requirements["relationships"] = True

        return requirements

    def _calculate_confidence(self, features: list[str], keywords: list[str]) -> float:
        """Calculate confidence score for the analysis."""
        confidence = 0.0

        # Base confidence from features identified
        if len(features) >= 3:
            confidence += 0.4
        elif len(features) >= 1:
            confidence += 0.2

        # Confidence from technical keywords
        if len(keywords) >= 5:
            confidence += 0.3
        elif len(keywords) >= 2:
            confidence += 0.2

        # Confidence from pattern matches
        pattern_matches = sum(
            1 for feature in features if any(feature.lower().replace(" ", "_") in self.feature_patterns)
        )
        if pattern_matches >= 2:
            confidence += 0.3
        elif pattern_matches >= 1:
            confidence += 0.1

        return min(confidence, 1.0)  # Cap at 100%
