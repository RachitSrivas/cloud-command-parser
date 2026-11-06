import json
from worker.clean import VALID_INTENTS, EXPECTED_KEYS


def test_intents_are_eight():
    """Verify that there are exactly eight allowed intents."""
    assert len(VALID_INTENTS) == 8
    expected = {
        "alarm_set",
        "alarm_query",
        "calendar_set",
        "calendar_query",
        "calendar_remove",
        "weather_query",
        "datetime_query",
        "recommendation_events",
    }
    assert VALID_INTENTS == expected


def test_expected_keys():
    """Verify expected 4 keys."""
    assert EXPECTED_KEYS == {"intent", "date", "time", "place"}
