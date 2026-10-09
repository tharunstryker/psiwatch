"""
text.py — Free-text column drift detection for psiwatch (v0.15.0).

Pure Python. Zero dependencies. No embeddings, no models, no downloads.

Why this exists
---------------
A column of sentences (chatbot messages, reviews, support tickets, search
queries) used to be treated as a categorical column where every unique
sentence is its own "category". That produces meaningless results: every new
sentence is a "new category", PSI explodes, and nothing tells you *what*
changed. This module analyses text the way text actually behaves.

What it measures (per text column)
----------------------------------
1. Vocabulary drift     Jensen-Shannon divergence (bits, 0..1) between the
                        word distributions, with an analytic small-sample
                        noise-floor correction so two samples from the same
                        source score ~0 instead of "a little drifted".
2. Explanations         Which words are rising, falling, or brand-new
                        (e.g. "refund", "scam" appearing in chatbot traffic).
3. Unseen-word rate     Share of new words never seen in the baseline,
                        corrected with the Good-Turing estimate so a small
                        baseline doesn't cause false alarms.
4. Script / language    Share of values per writing system (Latin, Tamil,
                        Devanagari, Arabic, CJK ...). Catches a sudden wave
                        of Tamil-script or transliterated traffic.
5. Length drift         Words-per-value, via the existing numeric analyser
                        (mean shift, std shift, PSI).
6. Structure drift      Empty rate, duplicate rate, URL rate, digit / upper-
                        case / symbol ratios. Catches bots, spam, templated
                        or injected input. Capped at MEDIUM severity.

Everything is computed from a bounded fingerprint (top-K vocabulary with
counts + a few scalars), so locked baselines stay small (tens of KB) and
never contain raw text.

Unicode: tokenisation treats combining marks as part of a word, so Tamil,
Hindi, Bengali etc. are not shredded at vowel signs. CJK characters are
tokenised one per token. Case is folded; pure digit tokens become <num>;
URLs and e-mail addresses are removed before tokenising (and counted
separately as the URL rate).
"""

import math
import re
import unicodedata
from bisect import bisect_right
from collections import Counter

TEXT_VOCAB_SIZE = 1000    # baseline words kept in a fingerprint
TEXT_MIN_DOCS = 5         # minimum non-empty values per dataset to analyse
_MIN_BIN_COUNT = 5        # vocab bins with fewer combined tokens are merged
_TOP_TERMS = 5            # rising / falling terms reported
_TOP_EMERGING = 8         # brand-new terms reported
_LN2 = math.log(2)
# Words inside one message are correlated (topic words cluster), so two
# samples from the SAME source diverge more than a plain multinomial predicts.
# Simulations on clustered synthetic traffic show ~1.1-1.4x; 1.5 is a
# deliberately conservative safety margin so healthy data stays PASS.
_NOISE_INFLATION = 1.5


# ─── Tokenisation ─────────────────────────────────────────────────────────────

_STOPWORDS = frozenset("""
a about above after again all also am an and any are as at be because been
before being below between both but by can could did do does doing down during
each few for from further had has have having he her here hers him his how i if
in into is it its just me more most my no nor not now of off on once only or
other our out over own same she should so some such than that the their them
then there these they this those through to too under until up us very was we
were what when where which while who whom why will with would you your yours
""".split())

_URL_RE = re.compile(r"(?:https?://|www\.)\S+|\b[\w.+-]+@[\w-]+\.[\w.-]+", re.I)
_ASCII_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)*")
_NON_ALPHA_RE = re.compile(r"[^A-Za-z]")
_NON_UPPER_RE = re.compile(r"[^A-Z]")
_NON_DIGIT_RE = re.compile(r"\D")
_WORD_SPACE_RE = re.compile(r"[\w\s]")

# (start, end, name) — sorted, non-overlapping. Letters only (callers filter
# with str.isalpha()), so punctuation inside a range is never counted.
_SCRIPT_RANGES = [
    (0x0041, 0x024F, "Latin"), (0x0370, 0x03FF, "Greek"),
    (0x0400, 0x052F, "Cyrillic"), (0x0590, 0x05FF, "Hebrew"),
    (0x0600, 0x06FF, "Arabic"), (0x0750, 0x077F, "Arabic"),
    (0x0900, 0x097F, "Devanagari"), (0x0980, 0x09FF, "Bengali"),
    (0x0A00, 0x0A7F, "Gurmukhi"), (0x0A80, 0x0AFF, "Gujarati"),
    (0x0B00, 0x0B7F, "Odia"), (0x0B80, 0x0BFF, "Tamil"),
    (0x0C00, 0x0C7F, "Telugu"), (0x0C80, 0x0CFF, "Kannada"),
    (0x0D00, 0x0D7F, "Malayalam"), (0x0D80, 0x0DFF, "Sinhala"),
    (0x0E00, 0x0E7F, "Thai"), (0x1000, 0x109F, "Myanmar"),
    (0x10A0, 0x10FF, "Georgian"), (0x1100, 0x11FF, "Hangul"),
    (0x1E00, 0x1EFF, "Latin"), (0x3040, 0x30FF, "Japanese"),
    (0x3400, 0x4DBF, "CJK"), (0x4E00, 0x9FFF, "CJK"),
    (0xAC00, 0xD7AF, "Hangul"), (0xFF21, 0xFF3A, "Latin"),
    (0xFF41, 0xFF5A, "Latin"),
]
_SCRIPT_STARTS = [r[0] for r in _SCRIPT_RANGES]


def _script_of(ch):
    o = ord(ch)
    i = bisect_right(_SCRIPT_STARTS, o) - 1
    if i >= 0 and o <= _SCRIPT_RANGES[i][1]:
        return _SCRIPT_RANGES[i][2]
    return "Other"


def _is_cjk(ch):
    o = ord(ch)
    return (0x3400 <= o <= 0x4DBF or 0x4E00 <= o <= 0x9FFF or
            0x3040 <= o <= 0x30FF or 0xAC00 <= o <= 0xD7AF)


def tokenize(text):
    """
    Split text into lowercase word tokens. Unicode-aware: combining marks stay
    attached to their word (Tamil/Hindi vowel signs), CJK is one token per
    character, apostrophes inside words are kept ("don't").
    """
    return _scan_text(text)[0]


def _flush(buf, tokens):
    if buf:
        tok = "".join(buf).strip("'")
        if tok:
            tokens.append(tok)
        del buf[:]


def _scan_unicode(body):
    """Slow path for non-ASCII text. Returns tokens + char stats."""
    tokens, buf = [], []
    letters = upper = digits = symbols = 0
    scripts = Counter()
    for ch in body:
        if _is_cjk(ch):
            _flush(buf, tokens)
            tokens.append(ch.lower())
            letters += 1
            scripts[_script_of(ch)] += 1
        elif ch.isalnum():
            buf.append(ch.lower())
            if ch.isalpha():
                letters += 1
                if ch.isupper():
                    upper += 1
                scripts[_script_of(ch)] += 1
            else:
                digits += 1
        elif ch == "'" or ch == "\u2019":
            symbols += 1
            if buf:
                buf.append("'")
        elif unicodedata.category(ch)[0] == "M":
            if buf:
                buf.append(ch)
        else:
            _flush(buf, tokens)
            if not ch.isspace():
                symbols += 1
    _flush(buf, tokens)
    script = scripts.most_common(1)[0][0] if scripts else "None"
    return tokens, letters, upper, digits, symbols, script


def _scan_text(body):
    """Tokens + character statistics for one (URL-stripped) document."""
    if body.isascii():
        tokens = _ASCII_TOKEN_RE.findall(body.lower())
        letters = len(_NON_ALPHA_RE.sub("", body))
        upper = len(_NON_UPPER_RE.sub("", body))
        digits = len(_NON_DIGIT_RE.sub("", body))
        symbols = len(_WORD_SPACE_RE.sub("", body))
        script = "Latin" if letters else "None"
        return tokens, letters, upper, digits, symbols, script
    return _scan_unicode(body)


def _terms(tokens):
    """Normalise tokens into vocabulary terms (drop stopwords, digits→<num>)."""
    out = []
    for tok in tokens:
        if tok.isdigit():
            out.append("<num>")
        elif tok in _STOPWORDS:
            continue
        elif len(tok) == 1 and tok.isascii():
            continue
        else:
            out.append(tok)
    return out


def _analyze_doc(text):
    """One document → (terms, n_words, script, digit_r, upper_r, symbol_r, has_url)."""
    has_url = False
    body = text
    if "http" in text or "www." in text or "@" in text:
        stripped, n = _URL_RE.subn(" ", text)
        if n:
            has_url = True
            body = stripped
    tokens, letters, upper, digits, symbols, script = _scan_text(body)
    n_chars = max(len(body.strip()), 1)
    return (
        _terms(tokens),
        len(tokens),
        script,
        digits / n_chars,
        (upper / letters) if letters else 0.0,
        symbols / n_chars,
        has_url,
    )


# ─── Column type detection ────────────────────────────────────────────────────

def looks_like_text(values):
    """
    Heuristic: is this (non-numeric) column free text rather than a
    categorical column? Free text = enough non-empty values, several words per
    value, and mostly-unique values. Multi-word categories such as
    "New York" (2 words, heavily repeated) stay categorical.
    """
    vals = [v for v in values if v and v.strip()]
    n = len(vals)
    if n < TEXT_MIN_DOCS:
        return False
    if n > 2000:
        step = n // 2000
        vals = vals[::step][:2000]
        n = len(vals)
    avg_words = sum(len(v.split()) for v in vals) / n
    avg_chars = sum(len(v) for v in vals) / n
    unique_ratio = len(set(vals)) / n
    if avg_words >= 3 and (unique_ratio > 0.5 or avg_words >= 8):
        return True
    # No-space scripts (Chinese, Japanese, Thai) have few "words" per value.
    return avg_chars >= 30 and unique_ratio > 0.5


# ─── Fingerprint ──────────────────────────────────────────────────────────────

def _scan(values):
    """Single pass over a column → full (untruncated) aggregates."""
    tc, dc = Counter(), Counter()
    word_counts = []
    scripts = Counter()
    seen = set()
    non_empty = dups = url_docs = 0
    digit_sum = upper_sum = symbol_sum = 0.0

    for v in values:
        t = v.strip() if isinstance(v, str) else str(v).strip()
        if not t:
            continue
        non_empty += 1
        h = hash(t.lower())
        if h in seen:
            dups += 1
        else:
            seen.add(h)
        terms, n_words, script, dr, ur, sr, has_url = _analyze_doc(t)
        word_counts.append(float(n_words))
        scripts[script] += 1
        tc.update(terms)
        dc.update(set(terms))
        digit_sum += dr
        upper_sum += ur
        symbol_sum += sr
        if has_url:
            url_docs += 1

    n = max(non_empty, 1)
    return {
        "docs": len(values),
        "non_empty": non_empty,
        "tc": tc,
        "dc": dc,
        "word_counts": word_counts,
        "scripts": scripts,
        "empty_rate": (len(values) - non_empty) / len(values) if values else 0.0,
        "duplicate_rate": dups / n,
        "style": {
            "digit_ratio": digit_sum / n,
            "upper_ratio": upper_sum / n,
            "symbol_ratio": symbol_sum / n,
            "url_rate": url_docs / n,
        },
    }


def build_text_summary(values, vocab_size=TEXT_VOCAB_SIZE):
    """
    Bounded statistical fingerprint of a text column — O(vocab_size) storage,
    never raw text. Used both live and by locker.py.
    """
    from .analyzer import build_numeric_summary

    agg = _scan(values)
    if agg["non_empty"] == 0:
        return None

    tc, dc = agg["tc"], agg["dc"]
    total_tokens = sum(tc.values())
    ranked = sorted(tc.items(), key=lambda kv: (-kv[1], kv[0]))
    top = ranked[:vocab_size]
    in_vocab = sum(c for _, c in top)

    scripts = agg["scripts"]
    return {
        "docs": agg["docs"],
        "non_empty": agg["non_empty"],
        "empty_rate": round(agg["empty_rate"], 6),
        "duplicate_rate": round(agg["duplicate_rate"], 6),
        "tokens": total_tokens,
        "vocab_size": len(tc),
        "vocab_truncated": len(tc) > vocab_size,
        "hapax": sum(1 for c in tc.values() if c == 1),
        "other_tokens": total_tokens - in_vocab,
        "vocab": {term: [c, dc[term]] for term, c in top},
        "length": build_numeric_summary(agg["word_counts"]),
        "scripts": dict(scripts),
        "style": {k: round(v, 6) for k, v in agg["style"].items()},
    }


# ─── Statistics ───────────────────────────────────────────────────────────────

def _jsd_bits(p_counts, q_counts):
    """Jensen-Shannon divergence in bits (0..1) + per-bin contributions."""
    n_p, n_q = sum(p_counts), sum(q_counts)
    contrib = []
    total = 0.0
    for pc, qc in zip(p_counts, q_counts):
        p, q = pc / n_p, qc / n_q
        m = (p + q) / 2
        c = 0.0
        if p > 0:
            c += 0.5 * p * math.log2(p / m)
        if q > 0:
            c += 0.5 * q * math.log2(q / m)
        contrib.append(c)
        total += c
    return total, contrib


def _jsd_noise_floor(k_eff, n_p, n_q, inflation=None):
    """
    Expected JSD (bits) between two samples of the SAME distribution, from
    the chi-square approximation JSD ≈ (1/8) Σ (p-q)²/m:
        E[JSD] ≈ (K-1)(1/n_p + 1/n_q) / (8 ln 2)
    multiplied by a conservative inflation factor for within-message word
    clustering (larger for tiny samples, where that clustering dominates).
    Subtracting this removes the small-sample inflation that
    makes naive JSD flag "drift" between two perfectly healthy small samples.
    """
    if k_eff < 2 or n_p == 0 or n_q == 0:
        return 0.0
    if inflation is None:
        inflation = _NOISE_INFLATION
    return inflation * (k_eff - 1) * (1.0 / n_p + 1.0 / n_q) / (8 * _LN2)


def _share(counter, n):
    return {k: v / n for k, v in counter.items()} if n else {}


def _pct(x):
    return round(100.0 * x, 1)


# ─── Analyzer ─────────────────────────────────────────────────────────────────

def _unknown(reason):
    return {"severity": "UNKNOWN", "reasons": [reason], "metrics": {}, "warnings": []}


def analyze_text(baseline_raw, new_raw, thresholds=None, baseline_summary=None):
    """
    Compare baseline vs new for a free-text column.

    Args:
        baseline_raw: list of raw baseline strings (ignored if
            baseline_summary is given — pass None in that case).
        new_raw: list of raw new strings.
        thresholds: optional threshold overrides.
        baseline_summary: optional build_text_summary() result (locked
            baselines).

    Returns the same shape as analyze_numeric / analyze_categorical.
    """
    from .analyzer import DEFAULT_THRESHOLDS, analyze_numeric, _worst

    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    b = baseline_summary if baseline_summary is not None else \
        build_text_summary(list(baseline_raw or []))
    new = _scan(list(new_raw or []))

    if b is None or b["non_empty"] < TEXT_MIN_DOCS or new["non_empty"] < TEXT_MIN_DOCS:
        return _unknown(
            f"Too few text values to analyse (need at least {TEXT_MIN_DOCS} "
            f"non-empty values in each dataset)"
        )

    severity = "PASS"
    reasons, warnings, metrics = [], [], {}
    b_docs, n_docs = b["non_empty"], new["non_empty"]

    if min(b_docs, n_docs) < 100:
        warnings.append(
            f"Small text sample (baseline={b_docs}, new={n_docs}) — vocabulary "
            f"drift is noise-corrected but has low statistical power under ~100 values"
        )
    ratio = max(b_docs, n_docs) / max(min(b_docs, n_docs), 1)
    if ratio > 10:
        warnings.append(
            f"Sample size mismatch: baseline={b_docs}, new={n_docs} "
            f"({ratio:.0f}x difference)"
        )

    metrics["baseline_count"] = b_docs
    metrics["new_count"] = n_docs

    # ── 1. Vocabulary drift (JSD, noise-corrected) ───────────────────────────
    vocab = b["vocab"]
    new_tc, new_dc = new["tc"], new["dc"]
    n_total = sum(new_tc.values())
    n_base = b["tokens"]

    if n_total == 0 or n_base == 0:
        warnings.append("No word tokens found in one of the datasets — vocabulary checks skipped")
        metrics["text_drift_score"] = None
    else:
        labels, p_list, q_list = [], [], []
        rare_p = b["other_tokens"]
        rare_q = n_total - sum(new_tc.get(term, 0) for term in vocab)
        for term, (pc, _) in vocab.items():
            qc = new_tc.get(term, 0)
            if pc + qc < _MIN_BIN_COUNT:
                rare_p += pc
                rare_q += qc
            else:
                labels.append(term)
                p_list.append(pc)
                q_list.append(qc)
        labels.append(None)           # None == "all other words"
        p_list.append(rare_p)
        q_list.append(rare_q)

        raw_jsd, contrib = _jsd_bits(p_list, q_list)
        k_eff = sum(1 for pc, qc in zip(p_list, q_list) if pc + qc > 0)
        # Tiny samples are bursty (a few messages dominate), so inflate the
        # floor further as the number of values shrinks: 1.5 + 25/min_docs.
        inflation = _NOISE_INFLATION + 25.0 / min(b_docs, n_docs)
        floor = _jsd_noise_floor(k_eff, n_base, n_total, inflation)
        score = max(0.0, raw_jsd - floor)

        metrics["text_drift_score"] = round(score, 4)
        metrics["jsd_raw"] = round(raw_jsd, 4)
        metrics["jsd_noise_floor"] = round(floor, 4)

        rising, falling = [], []
        if score > 0:
            n_p_tok, n_q_tok = sum(p_list), sum(q_list)
            ranked = sorted(
                (i for i in range(len(labels)) if labels[i] is not None),
                key=lambda i: -contrib[i],
            )
            for i in ranked:
                term = labels[i]
                p, q = p_list[i] / n_p_tok, q_list[i] / n_q_tok
                entry = {
                    "term": term,
                    "baseline_doc_pct": _pct(vocab[term][1] / b_docs),
                    "new_doc_pct": _pct(new_dc.get(term, 0) / n_docs),
                }
                if q > p and len(rising) < _TOP_TERMS:
                    rising.append(entry)
                elif q < p and len(falling) < _TOP_TERMS:
                    falling.append(entry)
                if len(rising) >= _TOP_TERMS and len(falling) >= _TOP_TERMS:
                    break
        metrics["rising_terms"] = rising
        metrics["falling_terms"] = falling

        if score > t["text_jsd_high"]:
            jsd_sev = "HIGH"
        elif score > t["text_jsd_medium"]:
            jsd_sev = "MEDIUM"
        else:
            jsd_sev = "PASS"
        if jsd_sev != "PASS":
            msg = (f"Vocabulary drift score {score:.3f} "
                   f"({'significant' if jsd_sev == 'HIGH' else 'moderate'}; "
                   f"noise floor {floor:.3f})")
            if rising:
                msg += " — rising: " + ", ".join(e["term"] for e in rising[:3])
            if falling:
                msg += "; falling: " + ", ".join(e["term"] for e in falling[:3])
            reasons.append(msg)
        severity = _worst(severity, jsd_sev)

        # ── 2. Emerging terms (not in baseline vocabulary) ───────────────────
        min_docs = max(3, math.ceil(0.01 * n_docs))
        emerging = [
            {"term": term, "new_doc_pct": _pct(c / n_docs)}
            for term, c in sorted(new_dc.items(), key=lambda kv: (-kv[1], kv[0]))
            if term not in vocab and c >= min_docs
        ][:_TOP_EMERGING]
        metrics["emerging_terms"] = emerging
        metrics["emerging_terms_approximate"] = bool(b["vocab_truncated"])
        if emerging and severity != "PASS":
            reasons.append(
                "New words not in baseline: " + ", ".join(e["term"] for e in emerging[:5])
            )

        # ── 3. Unseen-word rate (Good-Turing corrected) ──────────────────────
        new_oov = (n_total - sum(new_tc.get(term, 0) for term in vocab)) / n_total
        base_other = b["other_tokens"] / n_base
        hapax_share = b["hapax"] / n_base
        expected_oov = max(base_other, hapax_share)
        excess = new_oov - expected_oov
        metrics["new_unseen_word_rate"] = round(new_oov, 4)
        metrics["expected_unseen_word_rate"] = round(expected_oov, 4)
        if excess > t["text_oov_high"]:
            oov_sev = "HIGH"
        elif excess > t["text_oov_medium"]:
            oov_sev = "MEDIUM"
        else:
            oov_sev = "PASS"
        if oov_sev != "PASS":
            reasons.append(
                f"{new_oov * 100:.1f}% of words are unseen in the baseline "
                f"(expected ~{expected_oov * 100:.1f}%)"
            )
        severity = _worst(severity, oov_sev)

    metrics["baseline_vocab_size"] = b["vocab_size"]
    metrics["new_vocab_size"] = len(new_tc)

    # ── 4. Script / language mix ─────────────────────────────────────────────
    b_scripts = _share(Counter(b["scripts"]), b_docs)
    n_scripts = _share(new["scripts"], n_docs)
    shifts = {s: n_scripts.get(s, 0.0) - b_scripts.get(s, 0.0)
              for s in set(b_scripts) | set(n_scripts)}
    worst_shift = max((abs(v) for v in shifts.values()), default=0.0)
    metrics["scripts"] = {
        "baseline": {s: _pct(v) for s, v in sorted(b_scripts.items(), key=lambda kv: -kv[1])},
        "new": {s: _pct(v) for s, v in sorted(n_scripts.items(), key=lambda kv: -kv[1])},
    }
    if worst_shift > t["text_script_shift_high"]:
        script_sev = "HIGH"
    elif worst_shift > t["text_script_shift_medium"]:
        script_sev = "MEDIUM"
    else:
        script_sev = "PASS"
    if script_sev != "PASS":
        moved = [
            f"{('no letters' if s == 'None' else s)} {b_scripts.get(s, 0) * 100:.0f}% → "
            f"{n_scripts.get(s, 0) * 100:.0f}%"
            for s, v in sorted(shifts.items(), key=lambda kv: -abs(kv[1]))
            if abs(v) > t["text_script_shift_medium"]
        ]
        reasons.append("Writing-system mix shifted: " + ", ".join(moved))
    severity = _worst(severity, script_sev)

    # ── 5. Length (words per value) via the numeric analyser ─────────────────
    # Noise-aware thresholds: with few values, PSI / mean / std wobble by chance.
    # Widen the default boundaries by the expected null noise so a healthy
    # small sample isn't flagged. The margin vanishes as sample size grows.
    inv = 1.0 / b_docs + 1.0 / n_docs
    len_t = dict(t)
    # PSI on a 10-bin histogram is dominated by empty-bin artefacts with few
    # values, so it only gets a vote once both sides have >= 200 values.
    if min(b_docs, n_docs) >= 200:
        len_t["psi_medium"] = t["psi_medium"] + 9 * inv  # E[PSI | no drift], 10 bins
        len_t["psi_high"] = t["psi_high"] + 9 * inv
    else:
        len_t["psi_medium"] = len_t["psi_high"] = float("inf")
    mean_margin = 2 * math.sqrt(inv)
    std_margin = 2 * math.sqrt(inv / 2)
    len_t["mean_shift_medium"] = t["mean_shift_medium"] + mean_margin
    len_t["mean_shift_high"] = t["mean_shift_high"] + mean_margin
    len_t["std_shift_medium"] = t["std_shift_medium"] + std_margin
    len_t["std_shift_high"] = t["std_shift_high"] + std_margin
    length = analyze_numeric(None, new["word_counts"], thresholds=len_t,
                             baseline_summary=b["length"])
    lm = length.get("metrics", {})
    if length["severity"] != "UNKNOWN":
        metrics["baseline_words_mean"] = lm.get("baseline_mean")
        metrics["new_words_mean"] = lm.get("new_mean")
        metrics["baseline_words_median"] = lm.get("baseline_median")
        metrics["new_words_median"] = lm.get("new_median")
        metrics["length_psi"] = lm.get("psi")
        for r in length.get("reasons", []):
            reasons.append(f"Words per value: {r}")
        severity = _worst(severity, length["severity"])

        # analyze_numeric measures shifts in baseline-std units, so it is blind
        # when every baseline value has the same length (std == 0). Fall back
        # to a relative change of the mean.
        b_mean, n_mean = lm.get("baseline_mean"), lm.get("new_mean")
        if b["length"]["std"] == 0 and b_mean is not None and n_mean != b_mean:
            rel = abs(n_mean - b_mean) / max(b_mean, 1.0)
            if rel > t["std_shift_high"]:
                fb = "HIGH"
            elif rel > t["std_shift_medium"]:
                fb = "MEDIUM"
            else:
                fb = "PASS"
            if fb != "PASS":
                reasons.append(
                    f"Words per value: baseline length was constant ({b_mean:g} words) "
                    f"but is now {n_mean:g} on average"
                )
                severity = _worst(severity, fb)

    # ── 6. Structure (capped at MEDIUM) ──────────────────────────────────────
    struct_t = t["text_structure_shift"]
    checks = [
        ("Empty-value rate", b["empty_rate"], new["empty_rate"]),
        ("Duplicate rate", b["duplicate_rate"], new["duplicate_rate"]),
        ("URL/e-mail rate", b["style"]["url_rate"], new["style"]["url_rate"]),
        ("Digit share", b["style"]["digit_ratio"], new["style"]["digit_ratio"]),
        ("Upper-case share", b["style"]["upper_ratio"], new["style"]["upper_ratio"]),
        ("Symbol/emoji share", b["style"]["symbol_ratio"], new["style"]["symbol_ratio"]),
    ]
    metrics["structure"] = {
        name: {"baseline": round(bv, 4), "new": round(nv, 4)} for name, bv, nv in checks
    }
    for name, bv, nv in checks:
        if abs(nv - bv) > struct_t:
            reasons.append(f"{name} shifted {bv * 100:.1f}% → {nv * 100:.1f}%")
            severity = _worst(severity, "MEDIUM")

    return {"severity": severity, "reasons": reasons, "metrics": metrics,
            "warnings": warnings}
