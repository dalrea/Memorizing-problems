# -*- coding: utf-8 -*-
"""
Extract official explanations from the 해설집 PDFs and merge them into
src/data/questions.json (and the public copy).

Mapping rule
------------
Each 해설집 PDF corresponds to one exam date. The questions inside the PDF
are numbered 1..100, matching the same numbering used in questions.json.
So mapping is exam_date + question_no — we do NOT trust positional ordering
across the two PDFs separately.

Parsing
-------
* Reflow the PDF text in 2-column order (left col top→bottom, then right col),
  same as the body extractor. This preserves question/explanation order.
* Split the reflowed text by '<문제 해설>' segments. Each segment belongs to
  the question whose marker '<n>. ' most recently appeared before it.
* The explanation segment ends at the NEXT question marker on the same exam.
* Within a segment, remove all '[해설작성자 : … ]' bracketed credits but keep
  the prose around them. Multiple authors → just concatenate their text.
* Clean repeated header lines, page footer markers, choice-marker noise that
  may have leaked in.

If a question has no '<문제 해설>' block (rare — explanation was missing in
the source PDF), we leave its existing keyword-based explanation untouched.
"""

from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pdfplumber

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SRC_DATA = ROOT / "src" / "data"
PUBLIC_DATA = ROOT / "public" / "data"

EXPLAIN_DIR = ROOT / "pdf" / "explains"

HEADER_RE = re.compile(
    r"^\s*(?:"
    r"본 해설집은 최강 자격증.*|"
    r"정보처리기사\s*◐.*|"
    r"최강 자격증 기출문제.*|"
    r"전자문제집 CBT.*|"
    r"CBT\s*:\s*www\.comcbt\.com.*|"
    r"CBT\s*$|"
    r"기출문제 및 해설집.*|"
    r"기출문제 해설은 최강 자격증.*|"
    r"의해서 만들어진 자료입니다.*|"
    r"\d과목\s*:\s*[^\n]+|"
    r"www\.comcbt\.com.*|"
    r"아래와 같은 오류 신고가 있었습니다\.?\s*|"
    r"기출문제\s*및\s*해설집.*"
    r")$",
    re.MULTILINE,
)

AUTHOR_RE = re.compile(r"\[\s*해설\s*작성자\s*:\s*[^\]]*\]")

# Question marker at line start, with whitespace+real-word after the dot.
# We later reject markers that don't belong to the monotonic 1..100 sequence.
Q_MARKER_RE = re.compile(r"(?:(?<=\n)|^)(\d{1,3})\.\s+(?=[가-힣A-Za-z])")

EXPLAIN_TAG = "<문제 해설>"


def filename_to_date(name: str) -> str:
    m = re.search(r"(\d{8})", name)
    if not m:
        raise ValueError(name)
    s = m.group(1)
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"


def page_columns_text(page) -> str:
    """Reflow page words as left col (top→bottom) then right col."""
    words = page.extract_words(x_tolerance=2, y_tolerance=3, keep_blank_chars=False)
    if not words:
        return page.extract_text() or ""
    mid_x = page.width / 2.0

    def col_text(col):
        col.sort(key=lambda w: (round(float(w["top"]) / 3), float(w["x0"])))
        lines: Dict[int, List[dict]] = {}
        for w in col:
            key = int(round(float(w["top"]) / 3))
            lines.setdefault(key, []).append(w)
        out = []
        for key in sorted(lines):
            ws = sorted(lines[key], key=lambda w: float(w["x0"]))
            out.append(" ".join(w["text"] for w in ws))
        return "\n".join(out)

    left = [w for w in words if (float(w["x0"]) + float(w["x1"])) / 2 < mid_x]
    right = [w for w in words if (float(w["x0"]) + float(w["x1"])) / 2 >= mid_x]
    return col_text(left) + "\n" + col_text(right)


def reflowed_text(pdf_path: Path) -> str:
    parts: List[str] = []
    with pdfplumber.open(str(pdf_path)) as pl:
        for p in pl.pages:
            parts.append(page_columns_text(p))
    text = "\n".join(parts)
    # drop header / footer noise lines
    text = HEADER_RE.sub("", text)
    return text


_TAIL_NOISE_RE = re.compile(
    r"본 해설집의 저작권은[\s\S]*$|"
    r"카페,?\s*블로그 등의 업로드[\s\S]*$|"
    r"기출문제\s*및\s*해설집[\s\S]*$|"
    r"여러분들의 많은 의견 부탁[\s\S]*$|"
    r"\[오류 ?신고 ?내용\][\s\S]*$|"
    r"\[오류신고 ?반론\][\s\S]*$|"
    r"\[관리자[\s\S]*$",
)

_LINE_NOISE_RES = [
    re.compile(r"^\s*자격증 기출문제 정보처리기사.*$", re.MULTILINE),
    re.compile(r"^\s*정보처리기사\s*◐.*$", re.MULTILINE),
    re.compile(r"^\s*최강\s*◑.*$", re.MULTILINE),
    re.compile(r"^\s*최강\s*자격증.*$", re.MULTILINE),
    re.compile(r"^\s*CBT\s*:\s*www\.comcbt\.com.*$", re.MULTILINE),
    re.compile(r"^\s*아래와 같은 오류 신고가 있었습니다\.?\s*$", re.MULTILINE),
]


def clean_explanation(raw: str) -> str:
    s = raw
    # cut off everything from copyright/boilerplate tail markers onward
    s = _TAIL_NOISE_RE.sub("", s)
    # remove author credits
    s = AUTHOR_RE.sub("", s)
    # remove repeated <문제 해설> tags if they leaked
    s = s.replace("<문제 해설>", "")
    # remove individual noise lines (page headers/footers wedged inside)
    for r in _LINE_NOISE_RES:
        s = r.sub("", s)
    # collapse multiple blank lines
    s = re.sub(r"\n{3,}", "\n\n", s)
    lines = [ln.rstrip() for ln in s.splitlines()]
    out: List[str] = []
    prev_blank = False
    for ln in lines:
        is_blank = not ln.strip()
        if is_blank and prev_blank:
            continue
        out.append(ln)
        prev_blank = is_blank
    return "\n".join(out).strip()


_CHOICE_GLYPHS = "①②③④"


def _find_owner_marker(
    text: str, tag_pos: int, candidates: List[Tuple[int, int]],
) -> Tuple[int, int] | None:
    """For a '<문제 해설>' tag at `tag_pos`, find the question marker that
    owns it: the LAST marker before `tag_pos` whose stretch [marker_pos,
    tag_pos] contains all four choice glyphs ①②③④. Real markers' choices
    sit immediately above the tag; spurious markers (e.g. an explanation
    line '3. 순차 코드:') don't have their own choice block before the tag.
    """
    best: Tuple[int, int] | None = None
    for qn, pos in candidates:
        if pos >= tag_pos:
            break
        between = text[pos:tag_pos]
        if all(g in between for g in _CHOICE_GLYPHS):
            # also require the gap to be reasonably small — a real question
            # is rarely more than ~700 chars from its <문제 해설> tag.
            if tag_pos - pos <= 1200:
                best = (qn, pos)
    return best


def parse_explanations(pdf_path: Path) -> Dict[int, str]:
    """Return {questionNo: explanation_text} for one exam date.

    Strategy: anchor on '<문제 해설>' tags. For each tag, the owner is the
    closest preceding question marker whose stretch up to the tag contains
    all four choice glyphs ①②③④ (i.e. the actual choice block). This
    rejects spurious markers like '3. 순차 코드:' inside another question's
    explanation, since those don't have ①②③④ between them and the tag.

    The explanation ends at the NEXT tag's owner marker, OR end of doc.
    """
    text = reflowed_text(pdf_path)

    candidates = [
        (int(m.group(1)), m.start()) for m in Q_MARKER_RE.finditer(text)
        if 1 <= int(m.group(1)) <= 100
    ]

    tag_positions: List[int] = []
    i = 0
    while True:
        i = text.find(EXPLAIN_TAG, i)
        if i == -1:
            break
        tag_positions.append(i)
        i += len(EXPLAIN_TAG)

    # Resolve owner for every tag first
    tag_owners: List[Tuple[int, int, int]] = []  # (tag_pos, owner_qn, owner_pos)
    for tag_pos in tag_positions:
        owner = _find_owner_marker(text, tag_pos, candidates)
        if owner is None:
            continue
        tag_owners.append((tag_pos, owner[0], owner[1]))

    explanations: Dict[int, str] = {}
    for idx, (tag_pos, qn, _opos) in enumerate(tag_owners):
        if qn in explanations:
            continue  # only the first <문제 해설> per question
        # block ends at the next tag's owner marker, OR end of doc
        if idx + 1 < len(tag_owners):
            end = tag_owners[idx + 1][2]  # next owner's marker position
        else:
            end = len(text)
        raw = text[tag_pos + len(EXPLAIN_TAG):end]
        cleaned = clean_explanation(raw)
        if cleaned:
            explanations[qn] = cleaned

    return explanations


def main():
    pdfs = sorted(EXPLAIN_DIR.glob("정보처리기사*.pdf"))
    if not pdfs:
        print(f"해설집 PDF가 없습니다: {EXPLAIN_DIR}", file=sys.stderr)
        sys.exit(1)

    # Build map: examDate → {questionNo → explanation}
    all_explanations: Dict[str, Dict[int, str]] = {}
    for pdf in pdfs:
        date = filename_to_date(pdf.name)
        print(f"[추출] {pdf.name}")
        exps = parse_explanations(pdf)
        print(f"  → {len(exps)}/100 문제에서 해설 추출")
        all_explanations[date] = exps

    # Merge into both questions.json files
    missing_per_date: Dict[str, List[int]] = {}
    for path in (SRC_DATA / "questions.json", PUBLIC_DATA / "questions.json"):
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        replaced = 0
        kept = 0
        for q in data:
            new = all_explanations.get(q["examDate"], {}).get(q["questionNo"])
            if new:
                q["explanation"] = new
                replaced += 1
            else:
                kept += 1
                missing_per_date.setdefault(q["examDate"], []).append(q["questionNo"])
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {path.name}: 공식 해설 {replaced}건 / 기존 보존 {kept}건")

    # Report misses once
    print()
    print("공식 해설을 찾지 못해 기존 키워드 해설을 유지한 문제:")
    for date in sorted(missing_per_date):
        qns = missing_per_date[date]
        # de-dup (we touched both copies)
        uniq = sorted(set(qns))
        print(f"  {date}: {len(uniq)}건 — {uniq[:12]}{'…' if len(uniq) > 12 else ''}")


if __name__ == "__main__":
    main()
