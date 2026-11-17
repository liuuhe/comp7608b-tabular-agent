import json

import pytest

from evaluation.audit_followup import recover_literal_json


def test_literal_replace_recovery_preserves_generated_program_without_eval():
    content = r'''{"job_id": "R03", "code": "import pandas as pd\nPLACEHOLDER".replace("PLACEHOLDER", "tables = {'audit': []}\n"), "issues": [], "valid": true}'''
    recovered, changes = recover_literal_json(content)
    assert recovered["code"] == "import pandas as pd\ntables = {'audit': []}\n"
    assert recovered["valid"] is True
    assert json.loads(json.dumps(recovered)) == recovered
    assert changes == [{"kind": "literal_string_replace", "line": 1, "occurrences": 1,
                        "source_characters": 31, "result_characters": 43}]


@pytest.mark.parametrize("expression", [
    '''{"code": __import__('os').system('touch /tmp/never')}''',
    '''{"code": "x".replace("x", open('/etc/passwd').read())}''',
    '''{"code": "x".format()}''',
    '''{"code": "x" * 100000000}''',
    '''{"code": "x".replace("x", "a"), "code": "other"}''',
    '''{"code": "x".replace("", "a")}''',
    '''{"code": "x", "issues": []}''',
])
def test_recovery_does_not_execute_arbitrary_expressions_or_change_meaning(expression):
    with pytest.raises(ValueError):
        recover_literal_json(expression)
