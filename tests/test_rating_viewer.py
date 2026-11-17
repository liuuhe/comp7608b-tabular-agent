"""The offline rater UI must preserve human blanks, identities and CSV text."""

import json
import re
import shutil
import subprocess

import pytest

from evaluation.ratings import read_sheet
from scripts.rating_viewer import FIELDS, HTML, build
from tabular_agent.storage import read_json, write_json


def test_viewer_uses_only_distributed_evidence_and_safely_embeds_text(tmp_path):
    distribute = tmp_path / "distribute"
    folder = distribute / "artifacts/anonymous"
    folder.mkdir(parents=True)
    (distribute / "INSTRUCTIONS.md").write_text("Independent human scoring")
    (tmp_path / "identity_key.json").write_text("PRIVATE_CONDITION_IDENTITY")
    write_json(folder / "input.json", {"category": "explicit", "csv": "../../data/hash/data.csv"})
    (folder / "question.md").write_text('Question </script><img onerror="bad">')
    (folder / "report.md").write_text("Untrusted model text")
    (folder / "documentation.txt").write_text("Field documentation")
    (folder / "reference.csv").write_text("value\n3\n")
    result = build(distribute)
    assert result["rating_rows"] == 1
    text = (distribute / "index.html").read_text()
    assert "PRIVATE_CONDITION_IDENTITY" not in text
    raw = re.search(r'<script id="pack-data" type="application/json">(.*?)</script>', text, re.S)[1]
    assert "</script>" not in raw and "<img" not in raw
    payload = json.loads(raw)
    assert payload["outputs"][0]["question"] == 'Question </script><img onerror="bad">'
    assert payload["expected"] == [{"id": "anonymous", "category": "explicit", "finding": "0"}]
    assert read_json(distribute / "viewer-manifest.json")["outputs"] == 1
    with pytest.raises(ValueError, match="overwrite"):
        build(distribute)


@pytest.mark.skipif(not shutil.which("node"), reason="CSV browser logic probe requires Node.js")
def test_browser_csv_roundtrip_preserves_zeros_blanks_and_quoted_multiline_notes(tmp_path):
    script = re.search(r'<script id="app">(.*?)</script>', HTML, re.S)[1]
    script = script.replace("__FIELDS__", json.dumps(FIELDS))
    probe = r'''
const assert=require('node:assert/strict');
const row=Object.fromEntries(FIELDS.map(k=>[k,'']));
Object.assign(row,{id:'anonymous',category:'explicit',finding:'0',answer_correct:'0',
 constraints_met:'1',causal_overstatement:'0',clarification_justified:'0',notes:'中文,"quoted"\nsecond line'});
assert.equal(complete(row),true);
const blank={...row,answer_correct:''};assert.equal(complete(blank),false);
assert.deepEqual(parseCSV(serializeCSV([row,blank])),[row,blank]);
assert.equal(validateRows([row],[row])[0].answer_correct,'0');
assert.throws(()=>validateRows([row,row],[row]));
assert.throws(()=>validateRows([{...row,id:'other'}],[row]));
assert.throws(()=>validateRows([{...row,answer_correct:'2'}],[row]));
const empty={...row,category:'exploration',finding:'0',correctness:'0',grounding:'0',usefulness:'0'};
assert.equal(complete(empty),true);assert.equal(complete({...empty,correctness:'1'}),false);
process.stdout.write(serializeCSV([row]));
'''
    path = tmp_path / "browser-probe.cjs"
    path.write_text(script + probe)
    result = subprocess.run(["node", str(path)], check=True, capture_output=True, text=True)
    exported = tmp_path / "rater-scored.csv"
    exported.write_text(result.stdout, encoding="utf-8")
    scores = read_sheet(exported, {("anonymous", 0): "explicit"})
    assert scores[("anonymous", 0)]["answer_correct"] == 0
