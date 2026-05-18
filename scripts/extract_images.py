# -*- coding: utf-8 -*-
"""
Auto-crop visual regions from the PDFs for questions flagged in needs-review.

Approach
--------
* For each PDF page, find the y-coordinate of every "<n>. " question marker via
  pdfplumber word coordinates, split into left/right columns by x.
* For each question that is in the needs-review set, locate its marker and the
  next marker in the same column → that vertical span is the question's block.
* Within that block, the "visual" lives between the question text and the
  first choice marker (①②③④❶❷❸❹). We crop that vertical sub-band only.
* Render the page once with pypdfium2 at 2x scale, crop, save as WEBP.
* Write the {visual:{type:"image", src:..., alt:...}} field back into
  questions.json.

The cropped band always covers the full column width so any inline label
(headers, axis labels) is preserved.
"""

from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SRC_DATA = ROOT / "src" / "data"
PUBLIC_DATA = ROOT / "public" / "data"
ASSETS_DIR = ROOT / "public" / "assets" / "questions"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# render scale
SCALE = 2.0
# how aggressively to trim margins
MARGIN_PX = 4
# webp quality
WEBP_Q = 70
# choice markers
CHOICE_MARKERS = set("①②③④❶❷❸❹")
Q_MARKER_RE = re.compile(r"^\s*(\d{1,3})\.\s")


def filename_to_date(name: str) -> str:
    m = re.search(r"(\d{8})", name)
    if not m:
        raise ValueError(name)
    s = m.group(1)
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"


def page_words_by_column(page) -> Tuple[List[dict], List[dict], float, float]:
    """Return (left_words, right_words, mid_x, page_width)."""
    words = page.extract_words(x_tolerance=2, y_tolerance=3, keep_blank_chars=False)
    mid_x = page.width / 2.0
    left, right = [], []
    for w in words:
        cx = (float(w["x0"]) + float(w["x1"])) / 2
        (left if cx < mid_x else right).append(w)
    left.sort(key=lambda w: float(w["top"]))
    right.sort(key=lambda w: float(w["top"]))
    return left, right, mid_x, page.width


def find_question_spans(
    words: List[dict],
) -> List[Tuple[int, float, float, List[dict]]]:
    """Find marker '<n>.' tokens in a column's word stream.

    Returns list of (questionNo, y_top_of_marker, x0_of_marker, all_words_in_column)
    sorted by y_top. Span end is computed by the caller.
    """
    starts: List[Tuple[int, float, float]] = []
    # Look for tokens like "12." or split "12" + "."
    for i, w in enumerate(words):
        text = w["text"]
        m = re.match(r"^(\d{1,3})\.$", text)
        if m:
            qn = int(m.group(1))
            if 1 <= qn <= 100:
                starts.append((qn, float(w["top"]), float(w["x0"])))
            continue
        # "12" followed by "."
        m = re.match(r"^(\d{1,3})$", text)
        if m and i + 1 < len(words):
            nxt = words[i + 1]
            if nxt["text"].startswith(".") and abs(float(nxt["top"]) - float(w["top"])) < 4:
                qn = int(m.group(1))
                if 1 <= qn <= 100:
                    starts.append((qn, float(w["top"]), float(w["x0"])))
    # dedupe: prefer first occurrence of a given questionNo per column
    seen = set()
    dedup = []
    for s in sorted(starts, key=lambda t: t[1]):
        if s[0] in seen:
            continue
        seen.add(s[0])
        dedup.append(s)
    return [(qn, ytop, x0, words) for (qn, ytop, x0) in dedup]


def find_first_choice_y(
    words: List[dict], y_start: float, y_end: float
) -> Optional[float]:
    """Return y_top of first choice marker within [y_start, y_end), else None."""
    candidates: List[float] = []
    for w in words:
        y = float(w["top"])
        if not (y_start <= y < y_end):
            continue
        t = w["text"]
        if not t:
            continue
        # check first char
        if t[0] in CHOICE_MARKERS:
            candidates.append(y)
        # or a standalone marker char
        elif any(c in CHOICE_MARKERS for c in t):
            candidates.append(y)
    if not candidates:
        return None
    return min(candidates)


def column_x_bounds(
    col_words: List[dict], page_width: float, is_left: bool
) -> Tuple[float, float]:
    if not col_words:
        if is_left:
            return 0.0, page_width / 2 - 5
        return page_width / 2 + 5, page_width
    xs0 = [float(w["x0"]) for w in col_words]
    xs1 = [float(w["x1"]) for w in col_words]
    return min(xs0) - 4, max(xs1) + 4


def is_mostly_blank(img: Image.Image) -> bool:
    """Return True if the image is mostly empty (page footer/header strip).

    A real diagram fills a tall area (height ≥ 60 PDF units → ~120 px @ 2x) AND
    has dark pixels spread across multiple horizontal bands. A page footer is a
    single thin line of text at the bottom → all dark pixels concentrate in one
    band.
    """
    g = img.convert("L")
    w, h = g.size
    if h < 60:
        # too short to contain a diagram
        # but still allow if very dark (small inline table)
        hist = g.histogram()
        total = sum(hist)
        return total == 0 or sum(hist[:128]) / total < 0.06
    # split vertically into 6 bands, count how many bands have meaningful ink
    bands_with_ink = 0
    step = h // 6
    for i in range(6):
        y0 = i * step
        y1 = h if i == 5 else (i + 1) * step
        band = g.crop((0, y0, w, y1))
        bhist = band.histogram()
        btotal = sum(bhist)
        if btotal == 0:
            continue
        if sum(bhist[:128]) / btotal >= 0.015:
            bands_with_ink += 1
    return bands_with_ink < 2


def crop_and_save(
    pil_page: Image.Image,
    bbox_pdf: Tuple[float, float, float, float],  # x0,y0,x1,y1 in PDF coords
    out_path: Path,
) -> bool:
    x0, y0, x1, y1 = bbox_pdf
    px = (int(x0 * SCALE) - MARGIN_PX, int(y0 * SCALE) - MARGIN_PX,
          int(x1 * SCALE) + MARGIN_PX, int(y1 * SCALE) + MARGIN_PX)
    px = (max(0, px[0]), max(0, px[1]),
          min(pil_page.width, px[2]), min(pil_page.height, px[3]))
    if px[2] <= px[0] or px[3] <= px[1]:
        return False
    crop = pil_page.crop(px)
    if crop.mode != "RGB":
        crop = crop.convert("RGB")
    if is_mostly_blank(crop):
        return False
    crop.save(out_path, "WEBP", quality=WEBP_Q, method=4)
    return True


def render_page(pdf_pdfium: pdfium.PdfDocument, page_index: int) -> Image.Image:
    page = pdf_pdfium[page_index]
    pil = page.render(scale=SCALE).to_pil()
    page.close()
    return pil


def load_needs_review_ids() -> Dict[str, str]:
    """Return {qid: reason} for entries that look visual."""
    p = SRC_DATA / "needs-review.json"
    if not p.exists():
        return {}
    rv = json.loads(p.read_text(encoding="utf-8"))
    out: Dict[str, str] = {}
    for r in rv:
        reason = r.get("reason", "")
        if "시각" in reason or "표" in reason or "트리" in reason or "그래프" in reason:
            out[r["id"]] = reason
    return out


def main():
    needs = load_needs_review_ids()
    print(f"이미지 추출 대상 후보: {len(needs)}건")

    # group by examDate
    by_date: Dict[str, List[int]] = {}
    for qid in needs:
        date = qid[:8]
        qn = int(qid[9:])
        by_date.setdefault(date, []).append(qn)

    pdfs = {filename_to_date(p.name).replace("-", ""): p for p in ROOT.glob("정보처리기사*.pdf")}
    if not pdfs:
        print("PDF 파일이 없습니다. 이미 정리되었다면 다시 받아오세요.", file=sys.stderr)
        sys.exit(1)

    saved: Dict[str, str] = {}  # qid → relative_path

    for date_key, qns in by_date.items():
        pdf_path = pdfs.get(date_key)
        if not pdf_path:
            print(f"  ! {date_key} PDF 없음, 건너뜀")
            continue
        print(f"[{date_key}] 처리 중 ({len(qns)}문제)…")

        pdf_pdfium = pdfium.PdfDocument(str(pdf_path))
        with pdfplumber.open(str(pdf_path)) as pl:
            # For each page, build column spans
            for page_index, pl_page in enumerate(pl.pages):
                left_words, right_words, mid_x, pw = page_words_by_column(pl_page)
                left_spans = find_question_spans(left_words)
                right_spans = find_question_spans(right_words)
                page_height = pl_page.height
                rendered: Optional[Image.Image] = None

                for col_idx, (spans, words) in enumerate(
                    ((left_spans, left_words), (right_spans, right_words))
                ):
                    is_left = col_idx == 0
                    x_lo, x_hi = column_x_bounds(words, pw, is_left)
                    for i, (qn, ytop, x0_marker, _ws) in enumerate(spans):
                        qid = f"{date_key}-{qn:03d}"
                        if qid not in needs:
                            continue
                        # end y: next marker in same column or end of page
                        y_end = spans[i + 1][1] if i + 1 < len(spans) else page_height
                        # visual band: between first-choice marker and y_end? No —
                        # The visual is typically between question text and choices.
                        # We need the choice y_top within the block.
                        first_choice_y = find_first_choice_y(words, ytop, y_end)
                        # Visual band: from (some way below question marker) to first_choice_y
                        if first_choice_y is None:
                            # no choices found → take from a small offset down to y_end
                            visual_y0 = ytop + 14
                            visual_y1 = min(y_end, ytop + 200)
                        else:
                            visual_y0 = ytop + 14
                            visual_y1 = first_choice_y - 2
                        # require minimum height to be worth saving
                        if visual_y1 - visual_y0 < 24:
                            continue

                        if rendered is None:
                            rendered = render_page(pdf_pdfium, page_index)

                        out_name = f"{qid}.webp"
                        out_path = ASSETS_DIR / out_name
                        ok = crop_and_save(
                            rendered, (x_lo, visual_y0, x_hi, visual_y1), out_path
                        )
                        if ok and out_path.exists() and out_path.stat().st_size > 1200:
                            saved[qid] = f"assets/questions/{out_name}"
                        elif out_path.exists():
                            out_path.unlink()

        pdf_pdfium.close()

    print(f"\n저장된 이미지: {len(saved)}개")

    # ── update questions.json (both copies) ──────────────────────────────────
    for path in (SRC_DATA / "questions.json", PUBLIC_DATA / "questions.json"):
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        attached = 0
        cleared = 0
        for q in data:
            rel = saved.get(q["id"])
            if rel:
                q["visual"] = {
                    "type": "image",
                    "src": rel,
                    "alt": f"문제 {q['questionNo']}번 시각 자료",
                }
                attached += 1
                continue
            # otherwise drop any previously attached image-typed visual whose file is missing
            v = q.get("visual")
            if v and v.get("type") == "image":
                src_rel = v.get("src", "")
                p = ROOT / "public" / src_rel.lstrip("/")
                if not p.exists():
                    q.pop("visual", None)
                    cleared += 1
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  {path.name}: visual 첨부 {attached}건 / 정리 {cleared}건")


if __name__ == "__main__":
    main()
