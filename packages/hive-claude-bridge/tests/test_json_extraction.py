"""
Unit tests for JSON extraction and validation
"""

import pytest
import json
from unittest.mock import Mock

from hive_claude_bridge.json_parser import JsonExtractor, JsonExtractionStrategy
from hive_claude_bridge.validators import BaseResponseValidator
from hive_claude_bridge.exceptions import ClaudeValidationError


class TestJsonExtractionStrategy:
    """Test JsonExtractionStrategy enum"""

    def test_strategy_values(self):
        """Test that all expected strategies exist"""
        assert JsonExtractionStrategy.STRICT_JSON
        assert JsonExtractionStrategy.MARKDOWN_CODE_BLOCK
        assert JsonExtractionStrategy.FIRST_JSON_OBJECT
        assert JsonExtractionStrategy.LAST_JSON_OBJECT


class TestJsonExtractor:
    """Test JsonExtractor functionality"""

    def test_extract_strict_json_valid(self):
        """Test strict JSON extraction with valid JSON"""
        extractor = JsonExtractor(strategy=JsonExtractionStrategy.STRICT_JSON)

        response = '{"key": "value", "number": 42}'
        result = extractor.extract(response)

        assert result == {"key": "value", "number": 42}

    def test_extract_strict_json_invalid(self):
        """Test strict JSON extraction with invalid JSON"""
        extractor = JsonExtractor(strategy=JsonExtractionStrategy.STRICT_JSON)

        response = 'This is not JSON'

        with pytest.raises(ClaudeValidationError) as exc_info:
            extractor.extract(response)

        assert "Invalid JSON" in str(exc_info.value)

    def test_extract_markdown_code_block_valid(self):
        """Test markdown code block extraction"""
        extractor = JsonExtractor(strategy=JsonExtractionStrategy.MARKDOWN_CODE_BLOCK)

        response = '''
        Here's the analysis:

        ```json
        {
            "result": "success",
            "data": [1, 2, 3]
        }
        ```

        Hope this helps!
        '''

        result = extractor.extract(response)

        assert result == {"result": "success", "data": [1, 2, 3]}

    def test_extract_markdown_code_block_no_block(self):
        """Test markdown extraction when no code block exists"""
        extractor = JsonExtractor(strategy=JsonExtractionStrategy.MARKDOWN_CODE_BLOCK)

        response = 'No code block here'

        with pytest.raises(ClaudeValidationError) as exc_info:
            extractor.extract(response)

        assert "No JSON code block found" in str(exc_info.value)

    def test_extract_markdown_code_block_invalid_json(self):
        """Test markdown extraction with invalid JSON in block"""
        extractor = JsonExtractor(strategy=JsonExtractionStrategy.MARKDOWN_CODE_BLOCK)

        response = '''
        ```json
        {invalid json}
        ```
        '''

        with pytest.raises(ClaudeValidationError) as exc_info:
            extractor.extract(response)

        assert "Invalid JSON in code block" in str(exc_info.value)

    def test_extract_first_json_object(self):
        """Test extraction of first JSON object"""
        extractor = JsonExtractor(strategy=JsonExtractionStrategy.FIRST_JSON_OBJECT)

        response = '''
        Some text before
        {"first": "object", "number": 1}
        More text
        {"second": "object", "number": 2}
        '''

        result = extractor.extract(response)

        assert result == {"first": "object", "number": 1}

    def test_extract_last_json_object(self):
        """Test extraction of last JSON object"""
        extractor = JsonExtractor(strategy=JsonExtractionStrategy.LAST_JSON_OBJECT)

        response = '''
        Some text before
        {"first": "object", "number": 1}
        More text
        {"second": "object", "number": 2}
        Final text
        '''

        result = extractor.extract(response)

        assert result == {"second": "object", "number": 2}

    def test_extract_no_json_objects(self):
        """Test extraction when no JSON objects found"""
        extractor = JsonExtractor(strategy=JsonExtractionStrategy.FIRST_JSON_OBJECT)

        response = 'No JSON objects in this text'

        with pytest.raises(ClaudeValidationError) as exc_info:
            extractor.extract(response)

        assert "No JSON objects found" in str(exc_info.value)

    def test_extract_with_nested_objects(self):
        """Test extraction with nested JSON objects"""
        extractor = JsonExtractor(strategy=JsonExtractionStrategy.FIRST_JSON_OBJECT)

        response = '''
        {
            "outer": {
                "inner": {
                    "deep": "value"
                },
                "array": [1, 2, {"nested": true}]
            },
            "simple": "field"
        }
        '''

        result = extractor.extract(response)

        expected = {
            "outer": {
                "inner": {"deep": "value"},
                "array": [1, 2, {"nested": True}]
            },
            "simple": "field"
        }

        assert result == expected

    def test_extract_with_arrays(self):
        """Test extraction with JSON arrays"""
        extractor = JsonExtractor(strategy=JsonExtractionStrategy.FIRST_JSON_OBJECT)

        response = '''
        [
            {"item": 1, "name": "first"},
            {"item": 2, "name": "second"}
        ]
        '''

        result = extractor.extract(response)

        expected = [
            {"item": 1, "name": "first"},
            {"item": 2, "name": "second"}
        ]

        assert result == expected

    def test_extract_with_special_characters(self):
        """Test extraction with special characters in JSON"""
        extractor = JsonExtractor(strategy=JsonExtractionStrategy.STRICT_JSON)

        response = json.dumps({
            "unicode": "Hello 🌍",
            "escape": "Line 1\nLine 2\tTabbed",
            "quotes": 'He said "Hello"'
        })

        result = extractor.extract(response)

        assert result["unicode"] == "Hello 🌍"
        assert result["escape"] == "Line 1\nLine 2\tTabbed"
        assert result["quotes"] == 'He said "Hello"'


class TestBaseResponseValidator:
    """Test BaseResponseValidator functionality"""

    def test_validate_required_fields_success(self):
        """Test successful validation of required fields"""
        validator = BaseResponseValidator()

        data = {
            "field1": "value1",
            "field2": "value2",
            "field3": 42
        }

        required_fields = ["field1", "field2"]

        # Should not raise exception
        validator.validate_required_fields(data, required_fields)

    def test_validate_required_fields_missing(self):
        """Test validation with missing required fields"""
        validator = BaseResponseValidator()

        data = {
            "field1": "value1"
            # Missing field2
        }

        required_fields = ["field1", "field2"]

        with pytest.raises(ClaudeValidationError) as exc_info:
            validator.validate_required_fields(data, required_fields)

        assert "Missing required field: field2" in str(exc_info.value)

    def test_validate_field_type_success(self):
        """Test successful field type validation"""
        validator = BaseResponseValidator()

        data = {
            "string_field": "hello",
            "int_field": 42,
            "float_field": 3.14,
            "bool_field": True,
            "list_field": [1, 2, 3],
            "dict_field": {"key": "value"}
        }

        # Should not raise exceptions
        validator.validate_field_type(data, "string_field", str)
        validator.validate_field_type(data, "int_field", int)
        validator.validate_field_type(data, "float_field", float)
        validator.validate_field_type(data, "bool_field", bool)
        validator.validate_field_type(data, "list_field", list)
        validator.validate_field_type(data, "dict_field", dict)

    def test_validate_field_type_wrong_type(self):
        """Test field type validation with wrong type"""
        validator = BaseResponseValidator()

        data = {"field": "not_a_number"}

        with pytest.raises(ClaudeValidationError) as exc_info:
            validator.validate_field_type(data, "field", int)

        assert "Expected int, got str" in str(exc_info.value)

    def test_validate_field_type_missing_field(self):
        """Test field type validation with missing field"""
        validator = BaseResponseValidator()

        data = {}

        with pytest.raises(ClaudeValidationError) as exc_info:
            validator.validate_field_type(data, "missing_field", str)

        assert "Field 'missing_field' not found" in str(exc_info.value)

    def test_validate_field_range_success(self):
        """Test successful field range validation"""
        validator = BaseResponseValidator()

        data = {"score": 75}

        # Should not raise exception
        validator.validate_field_range(data, "score", 0, 100)

    def test_validate_field_range_too_low(self):
        """Test field range validation with value too low"""
        validator = BaseResponseValidator()

        data = {"score": -5}

        with pytest.raises(ClaudeValidationError) as exc_info:
            validator.validate_field_range(data, "score", 0, 100)

        assert "must be between 0 and 100" in str(exc_info.value)

    def test_validate_field_range_too_high(self):
        """Test field range validation with value too high"""
        validator = BaseResponseValidator()

        data = {"score": 150}

        with pytest.raises(ClaudeValidationError) as exc_info:
            validator.validate_field_range(data, "score", 0, 100)

        assert "must be between 0 and 100" in str(exc_info.value)

    def test_validate_enum_value_success(self):
        """Test successful enum validation"""
        validator = BaseResponseValidator()

        data = {"status": "active"}

        valid_values = ["active", "inactive", "pending"]

        # Should not raise exception
        validator.validate_enum_value(data, "status", valid_values)

    def test_validate_enum_value_invalid(self):
        """Test enum validation with invalid value"""
        validator = BaseResponseValidator()

        data = {"status": "unknown"}

        valid_values = ["active", "inactive", "pending"]

        with pytest.raises(ClaudeValidationError) as exc_info:
            validator.validate_enum_value(data, "status", valid_values)

        assert "must be one of" in str(exc_info.value)
        assert "active" in str(exc_info.value)

    def test_validate_list_items_success(self):
        """Test successful list items validation"""
        validator = BaseResponseValidator()

        data = {"items": ["apple", "banana", "cherry"]}

        # Should not raise exception
        validator.validate_list_items(data, "items", str)

    def test_validate_list_items_wrong_type(self):
        """Test list items validation with wrong item type"""
        validator = BaseResponseValidator()

        data = {"items": ["apple", 123, "cherry"]}

        with pytest.raises(ClaudeValidationError) as exc_info:
            validator.validate_list_items(data, "items", str)

        assert "Item at index 1" in str(exc_info.value)
        assert "expected str, got int" in str(exc_info.value)

    def test_validate_list_items_not_a_list(self):
        """Test list items validation when field is not a list"""
        validator = BaseResponseValidator()

        data = {"items": "not_a_list"}

        with pytest.raises(ClaudeValidationError) as exc_info:
            validator.validate_list_items(data, "items", str)

        assert "is not a list" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])