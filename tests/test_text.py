"""
test_text.py — Free-text column drift (v0.15.0).

Covers tokenisation (incl. Tamil/CJK), type detection, the noise-floor
calibration (healthy data must stay PASS), real drift scenarios, language /
script drift, structure drift, lock round-trips, reports and the CLI flags.
"""

import json
import os
import random
import sys
import tempfile

import pytest

import psiwatch
from psiwatch.analyzer import analyze, build_text_summary
from psiwatch.loader import detect_type
from psiwatch.locker import save_lock, load_lock
from psiwatch.text import analyze_text, looks_like_text, tokenize


# ─── Synthetic traffic ────────────────────────────────────────────────────────

def _world(seed=7, n_topics=6, topic_vocab=150, common_vocab=400,
           topic_share=0.45, lo=5, hi=18):
    """Messages = Zipf-distributed common words + words from one topic per message."""
    r = random.Random(seed)
    common = [f"w{i}x" for i in range(common_vocab)]
    topics = [[f"t{k}q{i}z" for i in range(topic_vocab)] for k in range(n_topics)]
    cw = [1 / (i + 1) for i in range(common_vocab)]
    tw = [1 / (i + 1) for i in range(topic_vocab)]

    def doc(mix):
        k = r.choices(range(n_topics), weights=mix)[0]
        words = []
        for _ in range(r.randint(lo, hi)):
            if r.random() > topic_share:
                words.append(r.choices(common, cw)[0])
            else:
                words.append(r.choices(topics[k], tw)[0])
        return " ".join(words)
    return doc


SAME = [1] * 6
TAKEOVER = [0.2, 0.2, 0.2, 0.2, 0.2, 5]


# ─── Tokenisation ─────────────────────────────────────────────────────────────

def test_tokenize_basic_lowercase_and_apostrophes():
    assert tokenize("Don't PANIC, it's fine!") == ["don't", "panic", "it's", "fine"]


def test_tokenize_keeps_tamil_words_intact():
    """Combining vowel signs must not split a Tamil word into fragments."""
    toks = tokenize("எனக்கு பணம் திரும்ப வேண்டும்")
    assert toks == ["எனக்கு", "பணம்", "திரும்ப", "வேண்டும்"]


def test_tokenize_hindi_and_mixed_script():
    assert tokenize("मेरा order नहीं आया") == ["मेरा", "order", "नहीं", "आया"]


def test_tokenize_cjk_is_one_token_per_character():
    assert tokenize("退款申请") == ["退", "款", "申", "请"]


# ─── Type detection ───────────────────────────────────────────────────────────

def test_detect_type_free_text_vs_categorical_vs_numeric():
    r = random.Random(1)
    sentences = [" ".join(r.choice(["alpha", "beta", "gamma", "delta", "eps"])
                          for _ in range(6)) + f" {i}" for i in range(60)]
    assert detect_type(sentences) == "text"
    assert detect_type(["New York", "Chennai", "Delhi", "New York", "Delhi"] * 20) == "categorical"
    assert detect_type([str(i) for i in range(50)]) == "numeric"


def test_detect_type_text_can_be_disabled():
    sentences = [f"this is message number {i} about something" for i in range(60)]
    assert detect_type(sentences) == "text"
    assert detect_type(sentences, allow_text=False) == "categorical"


def test_looks_like_text_needs_enough_values():
    assert looks_like_text(["a long enough sentence here"] * 3) is False


def test_repeated_templated_values_stay_categorical():
    status = ["Order shipped to customer", "Order delivered to customer"] * 100
    assert detect_type(status) == "categorical"


# ─── Calibration: healthy data must stay healthy ──────────────────────────────

@pytest.mark.parametrize("n", [300, 1000])
def test_same_source_samples_pass(n):
    doc = _world()
    for _ in range(5):
        res = analyze_text([doc(SAME) for _ in range(n)], [doc(SAME) for _ in range(n)])
        assert res["severity"] == "PASS", res["reasons"]
        assert res["metrics"]["text_drift_score"] == 0.0


def test_noise_floor_tracks_raw_jsd_on_healthy_data():
    """Raw JSD between healthy samples should be close to the predicted floor."""
    doc = _world()
    res = analyze_text([doc(SAME) for _ in range(1000)], [doc(SAME) for _ in range(1000)])
    m = res["metrics"]
    assert m["jsd_raw"] > 0
    assert m["jsd_noise_floor"] >= m["jsd_raw"] * 0.9


def test_small_samples_warn_about_low_power():
    doc = _world()
    res = analyze_text([doc(SAME) for _ in range(40)], [doc(SAME) for _ in range(40)])
    assert any("Small text sample" in w for w in res["warnings"])


# ─── Drift scenarios ──────────────────────────────────────────────────────────

def test_topic_takeover_is_high():
    doc = _world()
    res = analyze_text([doc(SAME) for _ in range(400)], [doc(TAKEOVER) for _ in range(400)])
    assert res["severity"] == "HIGH"
    assert res["metrics"]["text_drift_score"] > 0.05
    assert res["metrics"]["rising_terms"]
    assert all(e["term"].startswith("t5q") for e in res["metrics"]["rising_terms"][:3])


def test_moderate_topic_mix_shift_is_at_least_medium_for_topical_text():
    doc = _world(topic_share=0.8, lo=4, hi=9)
    sev = [analyze_text([doc(SAME) for _ in range(300)],
                        [doc([1, 1, 1, 1, 3, 3]) for _ in range(300)])["severity"]
           for _ in range(5)]
    assert sum(s in ("MEDIUM", "HIGH") for s in sev) >= 4


def test_new_vocabulary_is_reported_with_unseen_word_rate():
    base = [f"where is my order number {i % 7} please" for i in range(300)]
    base = [b + (" thanks" if i % 3 else " sir") for i, b in enumerate(base)]
    new = [f"refund scam chargeback fraud money back {i % 5}" for i in range(300)]
    res = analyze_text(base, new)
    m = res["metrics"]
    assert res["severity"] == "HIGH"
    terms = [e["term"] for e in m["emerging_terms"]]
    assert "refund" in terms and "scam" in terms
    assert m["new_unseen_word_rate"] > 0.8
    assert any("unseen in the baseline" in r for r in res["reasons"])


def test_small_baseline_does_not_trigger_false_unseen_word_alarm():
    """Good-Turing correction: a 40-message baseline can't have seen every word."""
    doc = _world()
    res = analyze_text([doc(SAME) for _ in range(40)], [doc(SAME) for _ in range(400)])
    assert not any("unseen in the baseline" in r for r in res["reasons"])


def test_stopword_only_changes_do_not_create_rising_terms():
    base = [f"the quick brown fox number {i % 9} jumps" for i in range(200)]
    res = analyze_text(base, list(base))
    assert res["severity"] == "PASS"
    assert res["metrics"]["rising_terms"] == []


# ─── Language / script drift ──────────────────────────────────────────────────

def test_script_shift_to_tamil_is_flagged_high():
    english = [f"please send my order status update {i}" for i in range(200)]
    mixed = english[:100] + [f"என் ஆர்டர் எங்கே சொல்லுங்கள் {i}" for i in range(100)]
    res = analyze_text(english, mixed)
    m = res["metrics"]
    assert res["severity"] == "HIGH"
    assert m["scripts"]["new"]["Tamil"] == 50.0
    assert any("Writing-system mix shifted" in r and "Tamil" in r for r in res["reasons"])


def test_no_script_flag_when_mix_is_stable():
    docs = ([f"order status {i} please" for i in range(100)] +
            [f"என் ஆர்டர் {i} எங்கே" for i in range(100)])
    res = analyze_text(docs, list(docs))
    assert res["metrics"]["scripts"]["baseline"] == res["metrics"]["scripts"]["new"]
    assert not any("Writing-system" in r for r in res["reasons"])


# ─── Structure drift ──────────────────────────────────────────────────────────

def test_url_spam_wave_is_flagged_but_capped_at_medium():
    base = [f"how do i reset my password for account {i}" for i in range(200)]
    new = [f"how do i reset my password for account {i}" for i in range(100)] + \
          [f"how do i reset my password for account {i} http://x.test/{i}" for i in range(100)]
    res = analyze_text(base, new)
    assert res["severity"] == "MEDIUM"
    assert any("URL/e-mail rate" in r for r in res["reasons"])


def test_duplicate_flood_is_flagged():
    base = [f"unique customer question number {i} about billing" for i in range(200)]
    new = ["buy cheap pills now"] * 150 + base[:50]
    res = analyze_text(base, new)
    assert any("Duplicate rate" in r for r in res["reasons"])


def test_length_drift_is_flagged():
    short = [f"track order {i}" for i in range(300)]
    long_ = [" ".join(f"word{j}" for j in range(40)) + f" {i}" for i in range(300)]
    res = analyze_text(short, long_)
    assert any(r.startswith("Words per value") for r in res["reasons"])
    assert res["metrics"]["new_words_mean"] > res["metrics"]["baseline_words_mean"]


# ─── Edge cases ───────────────────────────────────────────────────────────────

def test_too_few_values_is_unknown_not_a_crash():
    res = analyze_text(["a b c", "d e f"], ["g h i"] * 3)
    assert res["severity"] == "UNKNOWN"


def test_empty_and_blank_values_are_handled():
    base = [f"hello there customer {i}" for i in range(50)] + [""] * 10
    new = [f"hello there customer {i}" for i in range(50)] + [""] * 40
    res = analyze_text(base, new)
    assert any("Empty-value rate" in r for r in res["reasons"])


def test_result_is_json_serializable():
    doc = _world()
    res = analyze_text([doc(SAME) for _ in range(200)], [doc(TAKEOVER) for _ in range(200)])
    json.dumps(res)


def test_summary_is_bounded_and_contains_no_raw_sentences():
    secret = "my secret password is hunter2 please keep private"
    docs = [f"{secret} {i}" for i in range(100)] + [f"normal message {i} here" for i in range(100)]
    summary = build_text_summary(docs)
    blob = json.dumps(summary)
    assert secret not in blob
    assert len(summary["vocab"]) <= 1000


# ─── analyze() integration ────────────────────────────────────────────────────

def _frames(n=400):
    doc = _world()
    r = random.Random(3)
    old = {"age": [str(r.randint(18, 60)) for _ in range(n)],
           "msg": [doc(SAME) for _ in range(n)]}
    new = {"age": [str(r.randint(18, 60)) for _ in range(n)],
           "msg": [doc(TAKEOVER) for _ in range(n)]}
    return old, new


def test_analyze_autodetects_text_column():
    old, new = _frames()
    res = analyze(old, new)
    assert res["columns"]["msg"]["type"] == "text"
    assert res["columns"]["msg"]["severity"] == "HIGH"
    assert res["columns"]["age"]["type"] == "numeric"
    assert "msg" in res["summary"]["drifted_columns"]


def test_detect_text_false_restores_categorical_behaviour():
    old, new = _frames(100)
    res = analyze(old, new, detect_text=False)
    assert res["columns"]["msg"]["type"] == "categorical"


def test_text_columns_forces_text_on_low_cardinality_column():
    old = {"intent": ["refund my order now", "track my parcel"] * 40}
    new = {"intent": ["cancel everything fraud", "scam money back"] * 40}
    assert analyze(old, new)["columns"]["intent"]["type"] == "categorical"
    forced = analyze(old, new, text_columns=["intent"])
    assert forced["columns"]["intent"]["type"] == "text"


def test_unknown_forced_text_column_warns():
    old, new = _frames(50)
    res = analyze(old, new, text_columns=["nope"])
    assert any("text_columns not found" in w for w in res["warnings"])


def test_compare_columns_text_flag():
    base = [f"where is my order number {i}" for i in range(60)]
    new = [f"i want a refund for item {i}" for i in range(60)]
    r = psiwatch.compare_columns(base, new, name="msg", text=True)
    assert r["columns"]["msg"]["type"] == "text"


# ─── Locking ──────────────────────────────────────────────────────────────────

@pytest.fixture
def lock_path():
    with tempfile.NamedTemporaryFile(suffix=".lock.json", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


def test_lock_roundtrip_matches_direct_comparison(lock_path):
    old, new = _frames()
    direct = analyze(old, new)
    save_lock(old, lock_path=lock_path)
    locked = load_lock(new, lock_path=lock_path)
    assert locked["columns"]["msg"]["type"] == "text"
    assert locked["columns"]["msg"]["severity"] == direct["columns"]["msg"]["severity"]
    assert (locked["columns"]["msg"]["metrics"]["text_drift_score"] ==
            direct["columns"]["msg"]["metrics"]["text_drift_score"])


def test_lock_file_stays_small_and_has_no_raw_text(lock_path):
    old, _ = _frames(2000)
    save_lock(old, lock_path=lock_path)
    assert os.path.getsize(lock_path) < 200_000
    with open(lock_path, encoding="utf-8") as f:
        text = f.read()
    assert old["msg"][0] not in text


def test_lock_info_handles_text_columns(lock_path, capsys):
    old, _ = _frames(100)
    save_lock(old, lock_path=lock_path)
    capsys.readouterr()
    psiwatch.lock_info(lock_path)
    out = capsys.readouterr().out
    assert "[text," in out


# ─── Reports ──────────────────────────────────────────────────────────────────

def test_html_report_escapes_text_metrics(tmp_path):
    base = [f"order {i} status update please" for i in range(60)]
    new = [f"refund {i} <img src=x onerror=alert(1)> now" for i in range(60)]
    out = tmp_path / "r.html"
    psiwatch.compare({"<b>col</b>": base}, {"<b>col</b>": new},
                     output=str(out), silent_save=True, text_columns=["<b>col</b>"])
    page = out.read_text(encoding="utf-8")
    assert "<img src=x" not in page
    assert "<b>col</b>" not in page
    assert "&lt;num&gt;" in page


def test_terminal_and_txt_reports_render_text_columns(tmp_path, capsys):
    old, new = _frames(200)
    out = tmp_path / "r.txt"
    psiwatch.compare(old, new, output=str(out), silent_save=True)
    txt = out.read_text(encoding="utf-8")
    assert "Vocab drift" in txt and "Rising" in txt
    psiwatch.compare(old, new)
    assert "Vocab drift" in capsys.readouterr().out


# ─── Trend / viz / CLI ────────────────────────────────────────────────────────

def test_trend_works_with_text_columns():
    old, new = _frames(200)
    res = psiwatch.analyze_trend([old, old, new])
    assert "msg" in res["column_history"]
    assert res["column_history"]["msg"]["severity_history"][-1] == "HIGH"


def test_plot_drift_handles_text_columns(tmp_path):
    pytest.importorskip("matplotlib")
    from psiwatch.viz import plot_drift
    old, new = _frames(200)
    out = tmp_path / "chart.png"
    plot_drift(old, new, output=str(out))
    assert out.exists() and out.stat().st_size > 0


def _write_csv(path, rows):
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["msg"])
        for r in rows:
            w.writerow([r])


def test_cli_text_columns_and_no_text_detect(tmp_path, monkeypatch, capsys):
    from psiwatch import cli
    doc = _world()
    old, new = tmp_path / "old.csv", tmp_path / "new.csv"
    _write_csv(old, [doc(SAME) for _ in range(300)])
    _write_csv(new, [doc(TAKEOVER) for _ in range(300)])

    monkeypatch.setattr(sys, "argv", ["psiwatch", "compare", str(old), str(new), "--silent"])
    cli.main()
    assert "[text]" in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", ["psiwatch", "compare", str(old), str(new),
                                      "--silent", "--no-text-detect"])
    cli.main()
    assert "[categorical]" in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", ["psiwatch", "summary", str(old), str(new),
                                      "--silent", "--text-columns", "msg"])
    cli.main()
    assert "msg" in capsys.readouterr().out


def test_config_recognises_text_keys(tmp_path):
    from psiwatch.config import load_config
    cfg = tmp_path / ".psiwatchrc"
    cfg.write_text(json.dumps({"text_columns": ["message"], "detect_text": False}))
    loaded = load_config(explicit_path=str(cfg), silent=True)
    assert loaded["text_columns"] == ["message"]
    assert loaded["detect_text"] is False
