import json
import pytest
from service.app import validate_prediction, EXPECTED_KEYS, VALID_INTENTS


def test_schema_valid_prediction():
    """Test that a correctly formatted 4-key JSON string passes validation."""
    raw = json.dumps({
        "intent": "alarm_set",
        "date": "tomorrow",
        "time": "seven am",
        "place": None
    })
    is_valid, parsed = validate_prediction(raw)
    assert is_valid is True
    assert set(parsed.keys()) == EXPECTED_KEYS
    assert parsed["intent"] in VALID_INTENTS
    assert parsed["date"] == "tomorrow"
    assert parsed["place"] is None


def test_schema_rejects_missing_keys():
    """Test that a JSON payload missing required keys fails validation."""
    raw = json.dumps({
        "intent": "weather_query",
        "place": "london"
    })
    is_valid, parsed = validate_prediction(raw)
    assert is_valid is False
    assert parsed is None


def test_schema_rejects_invalid_intent():
    """Test that an unrecognized intent fails validation."""
    raw = json.dumps({
        "intent": "book_flight",
        "date": None,
        "time": None,
        "place": "paris"
    })
    is_valid, parsed = validate_prediction(raw)
    assert is_valid is False
    assert parsed is None


def test_schema_rejects_invalid_json():
    """Test that invalid non-JSON strings fail validation."""
    is_valid, parsed = validate_prediction("not json at all")
    assert is_valid is False
    assert parsed is None


def test_schema_rejects_extra_keys():
    """Test that unexpected extra keys are rejected."""
    raw = json.dumps({
        "intent": "weather_query",
        "date": None,
        "time": None,
        "place": "tokyo",
        "extra_info": "sunny"
    })
    is_valid, parsed = validate_prediction(raw)
    assert is_valid is False
    assert parsed is None
