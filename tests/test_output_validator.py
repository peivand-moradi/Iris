from services.output_validator import validate_interpretation

VALID = {
    "heard": "Nice weather we're having.",
    "possible_meaning": "They may be joking that the weather is bad.",
    "why": "The visible heavy rain conflicts with the literal wording.",
    "certainty": "medium",
    "alternative": "They may genuinely enjoy rainy weather.",
    "visual_context_used": True,
    "spoken_summary": "They may be joking, but that is not certain.",
}


def test_valid_output_passes_through():
    result = validate_interpretation(VALID, thread_id="t1")
    assert result.success
    assert result.possible_meaning == VALID["possible_meaning"]
    assert result.certainty == "medium"
    assert result.thread_id == "t1"


def test_none_raw_produces_fallback():
    result = validate_interpretation(None, thread_id="t1", error="boom")
    assert not result.success
    assert result.certainty == "low"
    assert result.error == "boom"


def test_missing_field_produces_fallback():
    raw = {k: v for k, v in VALID.items() if k != "why"}
    result = validate_interpretation(raw, thread_id="t1")
    assert not result.success
    assert "why" in result.error


def test_invalid_certainty_produces_fallback():
    raw = {**VALID, "certainty": "very-high"}
    result = validate_interpretation(raw, thread_id="t1")
    assert not result.success


def test_empty_possible_meaning_produces_fallback():
    raw = {**VALID, "possible_meaning": "   "}
    result = validate_interpretation(raw, thread_id="t1")
    assert not result.success


def test_overlong_spoken_summary_produces_fallback():
    raw = {**VALID, "spoken_summary": "x" * 500}
    result = validate_interpretation(raw, thread_id="t1")
    assert not result.success


def test_percentage_confidence_produces_fallback():
    raw = {**VALID, "why": "I am 90% sure this is correct."}
    result = validate_interpretation(raw, thread_id="t1")
    assert not result.success


def test_non_bool_visual_context_used_produces_fallback():
    raw = {**VALID, "visual_context_used": "true"}
    result = validate_interpretation(raw, thread_id="t1")
    assert not result.success


def test_non_string_alternative_produces_fallback():
    raw = {**VALID, "alternative": 42}
    result = validate_interpretation(raw, thread_id="t1")
    assert not result.success


def test_null_alternative_is_allowed():
    raw = {**VALID, "alternative": None}
    result = validate_interpretation(raw, thread_id="t1")
    assert result.success
    assert result.alternative is None


def test_non_dict_raw_produces_fallback():
    result = validate_interpretation("not a dict", thread_id="t1")
    assert not result.success
