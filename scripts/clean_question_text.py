# -*- coding: utf-8 -*-
"""
Strip page-header/footer noise that leaked into questionText and choices.

The source PDFs have a per-page banner like:
    정보처리기사 ◐ 2020년 06월 06일 필기 기출문제 ◑ 전자문제집 CBT : www.comcbt.com
and a page-end footer:
    최강 자격증 기출문제 전자문제집 CBT : www.comcbt.com
When the column-aware extractor joined words across line breaks, fragments of
those banners ended up mid-sentence in some questions and choices.

This cleanup removes those fragments wherever they appear, then collapses
whitespace. No semantic content is touched.
"""

from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]

# Patterns are applied in order. Each removes a fragment that may appear
# anywhere within a string. Order matters: longer/more-specific patterns first
# so we don't leave dangling tokens behind.
NOISE_PATTERNS = [
    # End-of-PDF promo block that leaks into the last question's last choice.
    # Apply first because it's the longest pattern and may contain other
    # patterns as substrings.
    re.compile(
        r"기출문제\s*및\s*해설집\s*다운로드[\s\S]*$"
    ),
    re.compile(
        r"전자문제집\s*CBT\s*홈페이지[\s\S]*$"
    ),
    # Full banner: "(자격증) 기출문제 정보처리기사 ◐ YYYY년 MM월 DD일 필기 기출문제"
    re.compile(
        r"(?:최강\s*)?자격증\s*기출문제\s*정보처리기사\s*◐\s*\d{4}년\s*\d{2}월\s*\d{2}일\s*필기\s*기출문제"
    ),
    # Same banner without the leading "자격증 기출문제" prefix
    re.compile(
        r"정보처리기사\s*◐\s*\d{4}년\s*\d{2}월\s*\d{2}일\s*필기\s*기출문제"
    ),
    # Footer fragment: "최강 자격증 기출문제 전자문제집 CBT : www.comcbt.com"
    re.compile(r"최강\s*자격증\s*기출문제(?:\s*전자문제집)?(?:\s*CBT\s*:\s*www\.comcbt\.com)?"),
    # Shorter footer leak: "최강 ◑"
    re.compile(r"최강\s*◑"),
    # Lone "◐" / "◑" near edges (rare; only when surrounded by spaces)
    re.compile(r"(?<=\s)[◐◑](?=\s)"),
    # "CBT : www.comcbt.com" standalone
    re.compile(r"CBT\s*:\s*www\.comcbt\.com"),
    # "전자문제집 CBT" by itself
    re.compile(r"전자문제집\s*CBT"),
]


def clean_text(s: str) -> str:
    out = s
    for pat in NOISE_PATTERNS:
        out = pat.sub(" ", out)
    # collapse runs of whitespace and trim
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r"\s*\n\s*", "\n", out)
    out = re.sub(r"\n{2,}", "\n\n", out)
    return out.strip()


def main():
    changed_q = 0
    changed_c = 0
    for rel in ("src/data/questions.json", "public/data/questions.json"):
        p = ROOT / rel
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        local_q = 0
        local_c = 0
        for q in data:
            new_text = clean_text(q.get("questionText", ""))
            if new_text != q.get("questionText"):
                q["questionText"] = new_text
                local_q += 1
            for ch in q.get("choices", []):
                new_ch = clean_text(ch.get("text", ""))
                if new_ch != ch.get("text"):
                    ch["text"] = new_ch
                    local_c += 1
        p.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"{rel}: questionText {local_q}건 / choices {local_c}건 정리")
        changed_q += local_q
        changed_c += local_c

    print(f"\n총 questionText {changed_q}건, choices {changed_c}건")


if __name__ == "__main__":
    main()
