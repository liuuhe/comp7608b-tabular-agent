"""Use synthetic ratings only; actual adjudication must come from the human UI."""

import json
import re
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from test_human_sample import fill_fixture, study  # noqa: F401

from scripts import adjudicate, human_sample
from tabular_agent.storage import digest, read_json


@pytest.fixture
def session(study, monkeypatch):  # noqa: F811 - reuse the synthetic study fixture
    root, _, _, _, _, pack, _ = study
    monkeypatch.setattr(adjudicate, "validate", human_sample.validate)
    first, second = root / "first.csv", root / "second.csv"
    fill_fixture(pack / "rater-1.csv", first)
    fill_fixture(pack / "rater-2.csv", second, lambda r: r.update(answer_correct="1")
                 if r["category"] == "explicit" else None)
    initial = root / "initial"
    human_sample.collect(pack, first, second, initial, interim=True)
    return adjudicate.Adjudication(pack, initial, root / "decisions", actor="Synthetic tester")


def choices(session, value=0):
    return [{"id": d["id"], "finding": d["finding"], "dimension": d["dimension"],
             "score": value, "reason": "Synthetic fixture only."} for d in session.disputes]


def test_starts_unselected_restores_zero_draft_and_rejects_invalid_choices(session):
    assert session.state()["decisions"] == []
    assert not session.state()["finalized"]
    with pytest.raises(ValueError, match="完成"):
        session.save({"revision": 0, "decisions": []}, final=True)
    for bad in (True, 2, -1, "0"):
        with pytest.raises(ValueError, match="rubric"):
            session.save({"revision": 0, "decisions": choices(session, bad)})
    selected = choices(session)
    session.save({"revision": 0, "decisions": selected})
    assert session.state()["revision"] == 1
    restored = adjudicate.Adjudication(session.pack, session.initial, session.workspace,
                                      actor="Synthetic tester")
    assert restored.state()["decisions"] == selected
    assert not restored.state()["finalized"]
    with pytest.raises(ValueError, match="版本"):
        session.save({"revision": 0, "decisions": selected})
    with pytest.raises(ValueError, match="duplicate"):
        session.save({"revision": 1, "decisions": selected + selected[:1]})


def test_explicit_submission_preserves_originals_and_initial_agreement(session):
    original = {p: digest(p) for p in session.initial.iterdir() if p.is_file()}
    pack = human_sample.pack_hashes(session.pack)
    result = session.save({"revision": 0, "decisions": choices(session)}, final=True)
    assert result["status"] == "sample_protocol_complete"
    assert result["sample_outputs_rated"] == 27
    final = session.workspace / "final"
    summary = read_json(final / "summary/summary.json")
    initial = read_json(session.initial / "ratings_merged.json")
    assert summary["human_sample"]["initial_agreement"] == initial["initial_agreement"]
    assert summary["human_sample"]["unrated_full_grid_outputs"] > 0
    assert read_json(final / "submission.json")["adjudicator"] == "Synthetic tester"
    assert read_json(final / "submission.json")["resolved_sha256"] == digest(final / "resolved.csv")
    assert all(digest(p) == h for p, h in original.items())
    assert human_sample.pack_hashes(session.pack) == pack
    assert session.state()["finalized"]
    with pytest.raises(ValueError, match="正式保存"):
        session.save({"revision": 0, "decisions": choices(session)}, final=True)


def test_http_viewing_is_read_only_and_post_requires_local_token(session):
    server = adjudicate.server_for(session, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base) as response:
            html = response.read().decode()
        token = re.search(r"const TOKEN='([^']+)'", html)[1]
        with urlopen(base + "/api/state") as response:
            state = json.load(response)
        assert state["decisions"] == [] and not state["finalized"]
        assert 'a.download' not in html and 'window.open' not in html
        payload = json.dumps({"revision": 0, "decisions": choices(session)}).encode()
        for extra in ({}, {"X-Adjudication-Token": token, "Origin": "https://outside.example"}):
            with pytest.raises(HTTPError) as error:
                urlopen(Request(base + "/api/draft", data=payload, headers=extra))
            assert error.value.code == 403
        assert not (session.workspace / "draft.json").exists()
        with urlopen(Request(base + "/api/draft", data=payload,
                             headers={"X-Adjudication-Token": token})) as response:
            assert json.load(response)["revision"] == 1
        assert not (session.workspace / "final").exists()
        with pytest.raises(HTTPError) as error:
            urlopen(base + "/../identity_key.json")
        assert error.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
