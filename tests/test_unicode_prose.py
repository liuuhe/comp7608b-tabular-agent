"""Generation-time numeric exclusions must match the accepted report text contract."""

import json
import re
import unicodedata

import pytest

from tabular_agent.draft_contract import ProsePart


def transmitted_pattern():
    # Exercise JSON transport, including astral characters encoded as surrogate pairs.
    schema = json.loads(json.dumps(ProsePart.model_json_schema()))
    return re.compile(schema["properties"]["text"]["pattern"])


@pytest.mark.parametrize(
    "text",
    [
        " in January  ٢٠١١ is ",  # The actual v21 model output.
        "value ⑦",
        "value Ⅶ",
        "value ½",
        "value ²",
        "value 𝟙",
        "value 𑁦",
        "value 7",
        "value ７",
        "safe\n٢٠١١\n",
        "{{table.mean.0.value}}",
    ],
)
def test_numeric_and_placeholder_characters_are_excluded_before_generation(text):
    assert transmitted_pattern().fullmatch(text) is None
    with pytest.raises(ValueError):
        ProsePart(text=text)


@pytest.mark.parametrize(
    "text",
    [
        "平均值见表。",
        "The mean is ",
        "First bin: ",
        "minus − and multiplication ×",
        "prose\nwith\ttabs",
        "superscript ⁿ and subscript ₙ letters",
        "四个分组",
    ],
)
def test_non_numeric_language_and_spacing_remain_available(text):
    assert transmitted_pattern().fullmatch(text)
    assert ProsePart(text=text).text == text


def test_transmitted_pattern_covers_the_full_runtime_unicode_numeric_category():
    pattern = transmitted_pattern()
    mismatches = []
    for codepoint in range(0x110000):
        char = chr(codepoint)
        expected = char not in "{}" and not unicodedata.category(char).startswith("N")
        if bool(pattern.fullmatch(char)) != expected:
            mismatches.append(f"U+{codepoint:04X}")
            if len(mismatches) == 10:
                break
    assert not mismatches, mismatches
