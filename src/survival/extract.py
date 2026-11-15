"""Fixed-order, verbatim idea extraction with code-point offsets (V1.4.0; final-stage rules v2 in V1.4.2).

Rules (DREAM-Idea-Survival-Rubric-v0.1, extraction section):
* Prefer the requested numbering (I1-I5 initially, 1-5 finally). Otherwise take
  numbered items 1-5, otherwise record the whole answer as one unstructured block.
* Spans are verbatim slices of the delivered text: [start, end) in zero-based code
  points, end exclusive. Nothing is completed, merged, rewritten or invented.
* A slot never filled stays missing; it is never filled from elsewhere.
* An answer that did not end at EOS marks its last span "partial" (possibly cut).
* A final-stage "New idea" note is split off and recorded separately: it has no
  source and cannot earn survival credit, but its usefulness can be rated.
Semantic quality is never decided here; judges do that later, blind to arm.

V1.4.2 final-stage rules (AMENDMENTS 2026-11-01; initial stage unchanged):
R1 a top-level marker may be a digit followed by whitespace then "(" or "*" ("1 (Faithful ...)");
R2 with no plain-number markers, top-level I<n> headers (n 1-10) mark members;
R3 a member whose header (first line, first 160 chars) says "new idea" and cites no I1-I5 source is an
   unsourced final_new_idea note; a header that also cites a source stays a sourced member;
R4 sourced members beyond five are kept as final_excess rows, never slotted.
Final-stage markers labelled 1-10 are accepted, so a top-level "6." ends member 5.
"""
import re

# Top-level markers only: an indented nested list ("   2.") is not a new idea.
_MARK = r"(?m)^[>#*_\-]*\**[ \t]*"
INITIAL_MARK = re.compile(_MARK + r"I([1-5])\b")
NUMBER_MARK = re.compile(_MARK + r"(?:Idea[ \t]+)?([1-9])[ \t]*[.):\-]")
NEW_IDEA_MARK = re.compile(_MARK + r"New idea\b", re.I)
SOURCE_ID = re.compile(r"\bI([1-5])\b")
FINAL_NUMBER_MARK = re.compile(_MARK + r"(?:Idea[ \t]+)?(10|[1-9])(?:[ \t]*[.):\-]|[ \t]+(?=[(*]))")
FINAL_I_MARK = re.compile(_MARK + r"I(10|[1-9])\b")
FINAL_LABELS = {str(n) for n in range(1, 11)}
SLOTS = 5


def _ordered_spans(text, pattern, allowed):
    """First occurrence of each allowed label, in reading order; spans run to the next accepted marker."""
    found, seen = [], set()
    for m in pattern.finditer(text):
        label = m.group(1)
        if label in allowed and label not in seen:
            seen.add(label)
            found.append((label, m.start()))
    return [(label, start, found[i + 1][1] if i + 1 < len(found) else len(text))
            for i, (label, start) in enumerate(found)]


def _row(stage, slot, label, text, start, end, status, **extra):
    excerpt = text[start:end].rstrip()
    return {"stage": stage, "slot": slot, "label": label, "source_start_offset": start,
            "source_end_offset": start + len(excerpt), "verbatim_excerpt": excerpt,
            "delivered": True, "extraction_status": status, **extra}


def _missing(stage, slot):
    return {"stage": stage, "slot": slot, "label": None, "source_start_offset": None, "source_end_offset": None,
            "verbatim_excerpt": "", "delivered": False, "extraction_status": "missing"}


def extract(text, stage, *, finish_reason="eos"):
    """Return exactly SLOTS slot rows (plus, for finals, any New-idea notes) for one answer.

    stage: "initial" or "final". Every row carries source_field="answer".
    """
    if stage not in ("initial", "final"):
        raise ValueError("stage must be initial or final")
    notes = []
    body_end = len(text)
    if stage == "final":
        note = NEW_IDEA_MARK.search(text)
        if note:
            # Everything from the first New-idea marker on is the note section; it is never a sourced idea.
            body_end = note.start()
            notes.append(_row("final_new_idea", None, "new_idea", text, note.start(), len(text), "new_idea_note",
                              source_seed_ids=[]))
    body = text[:body_end]
    if stage == "final":
        return _final(text, body, notes, finish_reason)
    method = "requested_numbering"
    spans = _ordered_spans(body, INITIAL_MARK, set("12345"))
    if not spans:
        spans = _ordered_spans(body, NUMBER_MARK, set("12345"))
        method = "numbered_list"
    rows = []
    if not spans:
        stripped = body.strip()
        if stripped:
            start = body.index(stripped)
            rows.append(_row(stage, 1, None, body, start, start + len(stripped), "unstructured"))
        method = "unstructured" if stripped else "empty"
    else:
        for slot, (label, start, end) in enumerate(spans[:SLOTS], 1):
            rows.append(_row(stage, slot, ("I" if method == "requested_numbering" else "") + label,
                             body, start, end, "complete"))
    if finish_reason != "eos" and (rows or notes):
        (notes or rows)[-1]["extraction_status"] = "partial"  # the last text written may be cut off
    rows += [_missing(stage, slot) for slot in range(len(rows) + 1, SLOTS + 1)]
    for row in rows + notes:
        row["source_field"] = "answer"
        row["extraction_method"] = method
    return rows + notes


def _final(text, body, notes, finish_reason):
    """Final stage under rules R1-R4 (see module docstring)."""
    method, prefix = "requested_numbering", ""
    spans = _ordered_spans(body, FINAL_NUMBER_MARK, FINAL_LABELS)
    if not spans:
        spans = _ordered_spans(body, FINAL_I_MARK, FINAL_LABELS)
        method, prefix = ("i_label_headers", "I") if spans else (method, prefix)
    rows, excess, member_notes = [], [], []
    if not spans:
        stripped = body.strip()
        if stripped:
            start = body.index(stripped)
            rows.append(_row("final", 1, None, body, start, start + len(stripped), "unstructured"))
        method = "unstructured" if stripped else "empty"
    for label, start, end in spans:
        header = body[start:end].split("\n", 1)[0][:160]
        if "new idea" in header.lower() and not SOURCE_ID.search(header):  # R3 (refined: no cited source)
            member_notes.append(_row("final_new_idea", None, "new_idea", body, start, end, "new_idea_note",
                                     member_label=prefix + label))
        elif len(rows) < SLOTS:
            rows.append(_row("final", len(rows) + 1, prefix + label, body, start, end, "complete"))
        else:
            excess.append(_row("final_excess", None, prefix + label, body, start, end, "excess_member"))
    for row in rows + excess:
        row["source_seed_ids"] = sorted({"I" + x for x in SOURCE_ID.findall(row["verbatim_excerpt"])})
    for row in member_notes:
        row["source_seed_ids"] = []
    notes = member_notes + notes
    written = [r for r in rows + excess + notes]
    if finish_reason != "eos" and written:
        max(written, key=lambda r: r["source_start_offset"])["extraction_status"] = "partial"
    rows += [_missing("final", slot) for slot in range(len(rows) + 1, SLOTS + 1)]
    for row in rows + excess + notes:
        row["source_field"] = "answer"
        row["extraction_method"] = method
    return rows + excess + notes
