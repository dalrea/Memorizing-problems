# -*- coding: utf-8 -*-
"""
Extract 정보처리기사 questions from 교사용 PDFs.

Strategy
--------
* PDFs use 2-column layout. extract_text() interleaves both columns by y-line,
  which breaks question order. So we split each page at the horizontal midpoint
  using word-level coordinates from pdfplumber and reflow left column first.
* In question bodies, the correct choice is marked by a filled circled glyph
  (❶❷❸❹) instead of a hollow one (①②③④). We capture that as the body answer.
* The last page always contains a 100-cell answer table — we treat that as the
  authoritative source. If body and table disagree, the question is flagged
  to needs-review.
* Questions that look short, lost choices, or contain visual hints (트리/그래프
  /표/코드/SQL) are also flagged.

Output
------
src/data/questions.json        — final array (per spec; explanations may be empty)
src/data/needs-review.json     — entries needing manual review
public/data/questions.json     — copy served by the static site
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pdfplumber

# ── encoding fix for Windows consoles ────────────────────────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
OUT_SRC = ROOT / "src" / "data"
OUT_PUBLIC = ROOT / "public" / "data"
OUT_SRC.mkdir(parents=True, exist_ok=True)
OUT_PUBLIC.mkdir(parents=True, exist_ok=True)

SUBJECTS = [
    "소프트웨어 설계",
    "소프트웨어 개발",
    "데이터베이스 구축",
    "프로그래밍 언어 활용",
    "정보시스템 구축관리",
]

# Filled circled digits → answer number
FILLED_MAP = {"❶": 1, "❷": 2, "❸": 3, "❹": 4}
HOLLOW_MAP = {"①": 1, "②": 2, "③": 3, "④": 4}
ANY_CIRCLED = {**FILLED_MAP, **HOLLOW_MAP}

VISUAL_HINTS = ("트리", "그래프", "표는", "테이블", "다이어그램", "다음 그림", "[그림", "스키마")


def filename_to_date(name: str) -> str:
    m = re.search(r"(\d{8})", name)
    if not m:
        raise ValueError(f"날짜를 찾을 수 없습니다: {name}")
    s = m.group(1)
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"


def subject_no_from_q(q: int) -> int:
    return min(5, max(1, (q - 1) // 20 + 1))


# ─────────────────────────────────────────────────────────────────────────────
# Column-aware text reflow
# ─────────────────────────────────────────────────────────────────────────────
def page_columns_text(page) -> str:
    """Return text reflowed as: left column top→bottom, then right column."""
    words = page.extract_words(
        x_tolerance=2,
        y_tolerance=3,
        keep_blank_chars=False,
        use_text_flow=False,
    )
    if not words:
        return page.extract_text() or ""
    mid_x = page.width / 2.0

    def col_text(col_words):
        # group into lines by y
        col_words.sort(key=lambda w: (round(float(w["top"]) / 3), float(w["x0"])))
        lines: Dict[int, List[dict]] = {}
        for w in col_words:
            key = int(round(float(w["top"]) / 3))
            lines.setdefault(key, []).append(w)
        out_lines = []
        for key in sorted(lines):
            ws = sorted(lines[key], key=lambda w: float(w["x0"]))
            out_lines.append(" ".join(w["text"] for w in ws))
        return "\n".join(out_lines)

    left = [w for w in words if (float(w["x0"]) + float(w["x1"])) / 2 < mid_x]
    right = [w for w in words if (float(w["x0"]) + float(w["x1"])) / 2 >= mid_x]
    return col_text(left) + "\n" + col_text(right)


def full_text_for_pdf(path: Path) -> Tuple[str, str]:
    """Return (body_text_with_columns_reflowed, last_page_text_raw)."""
    out: List[str] = []
    last_raw = ""
    with pdfplumber.open(str(path)) as pdf:
        for i, p in enumerate(pdf.pages):
            txt = page_columns_text(p)
            out.append(txt)
            if i == len(pdf.pages) - 1:
                last_raw = p.extract_text() or ""
    return "\n".join(out), last_raw


# ─────────────────────────────────────────────────────────────────────────────
# Answer table parsing
# ─────────────────────────────────────────────────────────────────────────────
ANSWER_LINE_RE = re.compile(r"([①②③④❶❷❸❹])")


def parse_answer_table(last_page_text: str) -> Dict[int, int]:
    """The last page contains rows like:
       1 2 3 4 5 6 7 8 9 10
       ③ ③ ② ④ ④ ① ② ④ ③ ②
    """
    answers: Dict[int, int] = {}
    lines = [ln.strip() for ln in last_page_text.splitlines() if ln.strip()]
    pending_header: Optional[List[int]] = None
    for ln in lines:
        # header line: 10 consecutive small integers
        nums = re.findall(r"\b(\d{1,3})\b", ln)
        nums_int = [int(n) for n in nums]
        if len(nums_int) == 10 and all(1 <= n <= 100 for n in nums_int) and nums_int == list(
            range(nums_int[0], nums_int[0] + 10)
        ):
            pending_header = nums_int
            continue
        if pending_header:
            circled = ANSWER_LINE_RE.findall(ln)
            if len(circled) >= 10:
                for q, c in zip(pending_header, circled[:10]):
                    answers[q] = ANY_CIRCLED[c]
                pending_header = None
    return answers


# ─────────────────────────────────────────────────────────────────────────────
# Question parsing
# ─────────────────────────────────────────────────────────────────────────────
Q_START_RE = re.compile(r"(?:^|\n)\s*(\d{1,3})\.\s+")


def split_questions(text: str) -> List[Tuple[int, str]]:
    """Return list of (questionNo, raw_block) by splitting at line-start '<n>. '."""
    text = re.sub(r"최강 자격증 기출문제[^\n]*", "", text)
    text = re.sub(r"전자문제집 CBT[^\n]*", "", text)
    text = re.sub(r" ", " ", text)

    matches = list(Q_START_RE.finditer(text))
    out: List[Tuple[int, str]] = []
    for i, m in enumerate(matches):
        qn = int(m.group(1))
        if not 1 <= qn <= 100:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((qn, text[start:end].strip()))
    # dedupe — keep the longest block per question number
    bucket: Dict[int, str] = {}
    for qn, blk in out:
        if qn not in bucket or len(blk) > len(bucket[qn]):
            bucket[qn] = blk
    return sorted(bucket.items())


CHOICE_SPLIT_RE = re.compile(r"([①②③④❶❷❸❹])")


def parse_choices_and_body(block: str) -> Tuple[str, Dict[int, str], Optional[int]]:
    """Split a question block into (questionText, {1..4: choiceText}, bodyAnswer)."""
    # remove subject header banners that might appear inside
    block = re.sub(r"\d과목\s*:\s*[^\n]+", "", block)
    # find first circled marker
    m = CHOICE_SPLIT_RE.search(block)
    if not m:
        return block.strip(), {}, None
    body = block[: m.start()].strip()
    rest = block[m.start():]
    tokens = CHOICE_SPLIT_RE.split(rest)
    # tokens: ['', marker, text, marker, text, ...]
    choices: Dict[int, str] = {}
    body_ans: Optional[int] = None
    i = 1
    while i < len(tokens) - 1:
        mark = tokens[i]
        text = tokens[i + 1]
        i += 2
        no = ANY_CIRCLED.get(mark)
        if no is None:
            continue
        if mark in FILLED_MAP and body_ans is None:
            body_ans = no
        # stop accumulating if a fifth marker appears (next question's leakage)
        if no in choices:
            break
        # truncate at newline-newline (rare)
        clean = re.sub(r"\s+", " ", text).strip()
        choices[no] = clean
    # if we collected more than 4 due to noise, keep 1..4 only
    choices = {k: v for k, v in choices.items() if 1 <= k <= 4}
    return body, choices, body_ans


def looks_visual(text: str) -> bool:
    return any(h in text for h in VISUAL_HINTS)


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────
def process_pdf(path: Path):
    exam_date = filename_to_date(path.name)
    round_title = f"{exam_date[0:4]}년 {exam_date[5:7]}월 {exam_date[8:10]}일 필기"
    body_text, last_raw = full_text_for_pdf(path)

    answer_table = parse_answer_table(last_raw)
    questions_raw = split_questions(body_text)

    questions: List[dict] = []
    review: List[dict] = []

    for qn, block in questions_raw:
        if not 1 <= qn <= 100:
            continue
        qtext, choices, body_ans = parse_choices_and_body(block)
        # clean question text
        qtext_clean = re.sub(r"\s+", " ", qtext).strip()

        s_no = subject_no_from_q(qn)
        s_name = SUBJECTS[s_no - 1]
        qid = f"{exam_date.replace('-', '')}-{qn:03d}"

        table_ans = answer_table.get(qn)
        reasons: List[str] = []
        if len(choices) != 4:
            reasons.append(f"보기 개수 {len(choices)} (4가 아님)")
        if table_ans is None:
            reasons.append("정답표에서 정답을 찾지 못함")
        if body_ans is None:
            reasons.append("본문에서 정답 표시(❶❷❸❹) 미검출")
        if body_ans and table_ans and body_ans != table_ans:
            reasons.append(f"본문 정답({body_ans}) ≠ 정답표 정답({table_ans})")
        if looks_visual(qtext_clean) or looks_visual(block):
            reasons.append("표/트리/그래프/다이어그램 가능성 — 시각 자료 수동 재구성 필요")
        if len(qtext_clean) < 8:
            reasons.append("문제 본문이 너무 짧음")

        # answer choice: prefer table; fall back to body
        answer = table_ans if table_ans is not None else body_ans

        q_dict = {
            "id": qid,
            "examDate": exam_date,
            "roundTitle": round_title,
            "subjectNo": s_no,
            "subjectName": s_name,
            "questionNo": qn,
            "questionText": qtext_clean,
            "choices": [
                {"no": n, "text": choices.get(n, "")} for n in (1, 2, 3, 4)
            ],
            "answer": answer if answer in (1, 2, 3, 4) else 1,
            "explanation": "",
            "conceptTags": [s_name],
        }
        questions.append(q_dict)
        if reasons:
            review.append({"id": qid, "reason": " / ".join(reasons)})

    # ensure 100 entries — fill any missing with a needs-review stub
    have = {q["questionNo"] for q in questions}
    for qn in range(1, 101):
        if qn in have:
            continue
        s_no = subject_no_from_q(qn)
        qid = f"{exam_date.replace('-', '')}-{qn:03d}"
        questions.append(
            {
                "id": qid,
                "examDate": exam_date,
                "roundTitle": round_title,
                "subjectNo": s_no,
                "subjectName": SUBJECTS[s_no - 1],
                "questionNo": qn,
                "questionText": "(추출 실패: 수동 입력 필요)",
                "choices": [{"no": n, "text": ""} for n in (1, 2, 3, 4)],
                "answer": answer_table.get(qn, 1),
                "explanation": "",
                "conceptTags": [SUBJECTS[s_no - 1]],
            }
        )
        review.append({"id": qid, "reason": "추출 실패 — 본문 텍스트에서 문제 블록을 찾지 못함"})

    questions.sort(key=lambda q: q["questionNo"])
    return questions, review


def main():
    pdfs = sorted(ROOT.glob("정보처리기사*.pdf"))
    if not pdfs:
        print("PDF를 찾지 못했습니다. 작업 폴더에 정보처리기사*.pdf 를 두세요.", file=sys.stderr)
        sys.exit(1)

    all_questions: List[dict] = []
    all_review: List[dict] = []
    for p in pdfs:
        print(f"[추출] {p.name}")
        qs, rv = process_pdf(p)
        print(f"  - 문제 {len(qs)}개, 검토 {len(rv)}개")
        all_questions.extend(qs)
        all_review.extend(rv)

    OUT_SRC.mkdir(parents=True, exist_ok=True)
    OUT_PUBLIC.mkdir(parents=True, exist_ok=True)

    for target in (OUT_SRC, OUT_PUBLIC):
        (target / "questions.json").write_text(
            json.dumps(all_questions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (target / "needs-review.json").write_text(
            json.dumps(all_review, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(f"총 {len(all_questions)}문제, 검토 {len(all_review)}개를 저장했습니다.")


if __name__ == "__main__":
    main()
