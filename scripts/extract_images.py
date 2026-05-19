# -*- coding: utf-8 -*-
"""
Auto-crop visual regions from the PDFs for questions flagged in needs-review.

Two-pass strategy
-----------------
Pass 1 (same-column visual)
  * For each PDF page, find question markers in left/right columns.
  * Within a question's span [marker, next-marker], the visual lives between
    the question text and the first choice marker (①②③④❶❷❸❹).
  * Crop the column-wide band between those y-coords, scaled 2x.

Pass 2 (cross-column overflow)
  * Many questions start near the page bottom — their choices/visual flow into
    the TOP of the OPPOSITE column. We detect:
        same-column has NO choice markers in span
     OR same-column visual band is empty (filtered as blank)
    and then look for the visual at the top of the opposite column, ending at
    the opposite column's first choice marker.

We also exclude the page footer band (~bottom 35 PDF units) which contains the
"최강 자격증…" strip and a horizontal rule.
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

SCALE = 2.0
MARGIN_PX = 4
WEBP_Q = 70
# bottom strip on every page is the footer rule + branding — never visual
FOOTER_RESERVED_Y = 36  # PDF units from bottom

CHOICE_MARKERS = set("①②③④❶❷❸❹")


# ────────────────────────────────────────────────────────────────────────────
# PDF helpers
# ────────────────────────────────────────────────────────────────────────────
def filename_to_date(name: str) -> str:
    m = re.search(r"(\d{8})", name)
    if not m:
        raise ValueError(name)
    s = m.group(1)
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"


def page_words_by_column(page) -> Tuple[List[dict], List[dict], float, float]:
    words = page.extract_words(x_tolerance=2, y_tolerance=3, keep_blank_chars=False)
    mid_x = page.width / 2.0
    left, right = [], []
    for w in words:
        cx = (float(w["x0"]) + float(w["x1"])) / 2
        (left if cx < mid_x else right).append(w)
    left.sort(key=lambda w: float(w["top"]))
    right.sort(key=lambda w: float(w["top"]))
    return left, right, mid_x, page.width


def find_question_spans(words: List[dict]) -> List[Tuple[int, float, float]]:
    """Return [(qn, y_top, x0)] for marker tokens '<n>.' in the column."""
    starts: List[Tuple[int, float, float]] = []
    for i, w in enumerate(words):
        text = w["text"]
        m = re.match(r"^(\d{1,3})\.$", text)
        if m:
            qn = int(m.group(1))
            if 1 <= qn <= 100:
                starts.append((qn, float(w["top"]), float(w["x0"])))
            continue
        m = re.match(r"^(\d{1,3})$", text)
        if m and i + 1 < len(words):
            nxt = words[i + 1]
            if nxt["text"].startswith(".") and abs(float(nxt["top"]) - float(w["top"])) < 4:
                qn = int(m.group(1))
                if 1 <= qn <= 100:
                    starts.append((qn, float(w["top"]), float(w["x0"])))
    seen = set()
    dedup: List[Tuple[int, float, float]] = []
    for s in sorted(starts, key=lambda t: t[1]):
        if s[0] in seen:
            continue
        seen.add(s[0])
        dedup.append(s)
    return dedup


def find_first_choice_y(words: List[dict], y_start: float, y_end: float) -> Optional[float]:
    ys: List[float] = []
    for w in words:
        y = float(w["top"])
        if not (y_start <= y < y_end):
            continue
        t = w["text"]
        if t and (t[0] in CHOICE_MARKERS or any(c in CHOICE_MARKERS for c in t)):
            ys.append(y)
    return min(ys) if ys else None


def column_x_bounds(col_words: List[dict], page_width: float, is_left: bool) -> Tuple[float, float]:
    if not col_words:
        return (0.0, page_width / 2 - 5) if is_left else (page_width / 2 + 5, page_width)
    xs0 = [float(w["x0"]) for w in col_words]
    xs1 = [float(w["x1"]) for w in col_words]
    return min(xs0) - 4, max(xs1) + 4


# ────────────────────────────────────────────────────────────────────────────
# Image filtering / cropping
# ────────────────────────────────────────────────────────────────────────────
def is_mostly_blank(img: Image.Image) -> bool:
    """True if the image is too sparse to be a real diagram/table.

    Strategy: cut into 6 horizontal bands, count how many bands have ≥1.2%
    dark ink. Real diagrams have ink across multiple bands; footer strips have
    ink in only 1 band.
    """
    g = img.convert("L")
    w, h = g.size
    bands_with_ink = 0
    n_bands = 6
    step = max(1, h // n_bands)
    for i in range(n_bands):
        y0 = i * step
        y1 = h if i == n_bands - 1 else (i + 1) * step
        band = g.crop((0, y0, w, y1))
        bhist = band.histogram()
        btotal = sum(bhist)
        if btotal == 0:
            continue
        if sum(bhist[:128]) / btotal >= 0.012:
            bands_with_ink += 1
    return bands_with_ink < 2


def words_in_band(words: List[dict], y0: float, y1: float, x0: float, x1: float) -> int:
    n = 0
    for w in words:
        wy = float(w["top"])
        wx = (float(w["x0"]) + float(w["x1"])) / 2
        if y0 <= wy < y1 and x0 <= wx <= x1:
            n += 1
    return n


def crop(pil_page: Image.Image, bbox_pdf: Tuple[float, float, float, float]) -> Optional[Image.Image]:
    x0, y0, x1, y1 = bbox_pdf
    if y1 - y0 < 18 or x1 - x0 < 30:
        return None
    px = (
        int(x0 * SCALE) - MARGIN_PX, int(y0 * SCALE) - MARGIN_PX,
        int(x1 * SCALE) + MARGIN_PX, int(y1 * SCALE) + MARGIN_PX,
    )
    px = (max(0, px[0]), max(0, px[1]),
          min(pil_page.width, px[2]), min(pil_page.height, px[3]))
    if px[2] <= px[0] or px[3] <= px[1]:
        return None
    return pil_page.crop(px).convert("RGB")


# ────────────────────────────────────────────────────────────────────────────
# Extraction pipeline
# ────────────────────────────────────────────────────────────────────────────
def all_question_ids() -> List[str]:
    """We try image extraction for EVERY question; the blank filter rejects
    questions that have no real visual content. This avoids depending on
    keyword heuristics that miss many figures."""
    src = SRC_DATA / "questions.json"
    if not src.exists():
        return []
    data = json.loads(src.read_text(encoding="utf-8"))
    return [q["id"] for q in data]


def try_overflow_band(
    page_img: Image.Image,
    col_words: List[dict],
    col_spans: List[Tuple[int, float, float]],
    xl: float, xh: float,
    page_height: float, footer_y: float,
) -> Optional[Image.Image]:
    """Try to crop the top of a column where a continued question's visual
    sits before its choices. Returns the crop or None."""
    top = 80
    first_q_y = next((s[1] for s in col_spans if s[1] > top), page_height)
    fc_y = find_first_choice_y(col_words, top, first_q_y)
    end_raw = fc_y - 2 if fc_y else first_q_y - 4
    end = min(end_raw, footer_y)
    if end - top < 24:
        return None
    band_words = words_in_band(col_words, top, end, xl, xh)
    if band_words > 14:
        return None
    c = crop(page_img, (xl, top, xh, end))
    if c is None or is_mostly_blank(c):
        return None
    return c


def try_save(crop_img: Optional[Image.Image], out_path: Path) -> bool:
    if crop_img is None:
        return False
    if is_mostly_blank(crop_img):
        return False
    crop_img.save(out_path, "WEBP", quality=WEBP_Q, method=4)
    return out_path.exists() and out_path.stat().st_size > 800


def process_pdf(pdf_path: Path, target_qns_for_date: List[int]) -> Dict[int, str]:
    """Return {questionNo: relative_src} for questions we successfully cropped."""
    date_key = filename_to_date(pdf_path.name).replace("-", "")
    targets = set(target_qns_for_date)
    saved: Dict[int, str] = {}

    pdf_pdfium = pdfium.PdfDocument(str(pdf_path))
    rendered_cache: Dict[int, Image.Image] = {}

    def page_image(i: int) -> Image.Image:
        if i not in rendered_cache:
            pg = pdf_pdfium[i]
            rendered_cache[i] = pg.render(scale=SCALE).to_pil()
            pg.close()
        return rendered_cache[i]

    with pdfplumber.open(str(pdf_path)) as pl:
        # Collect column structures per page
        page_data = []
        for p in pl.pages:
            lw, rw, mx, pw = page_words_by_column(p)
            ls = find_question_spans(lw)
            rs = find_question_spans(rw)
            page_data.append(
                {
                    "page": p,
                    "width": pw,
                    "height": p.height,
                    "left_words": lw,
                    "right_words": rw,
                    "left_spans": ls,
                    "right_spans": rs,
                }
            )

        # Question → (page_index, column, marker_y)
        # We use spans only from the same page; cross-page handled separately.
        for page_index, pd in enumerate(page_data):
            ph = pd["height"]
            footer_y = ph - FOOTER_RESERVED_Y
            for col_name, words, spans, is_left in (
                ("L", pd["left_words"], pd["left_spans"], True),
                ("R", pd["right_words"], pd["right_spans"], False),
            ):
                xl, xh = column_x_bounds(words, pd["width"], is_left)
                for i, (qn, ytop, _) in enumerate(spans):
                    if qn not in targets:
                        continue
                    if qn in saved:
                        continue
                    y_end_same = spans[i + 1][1] if i + 1 < len(spans) else ph
                    fc_same = find_first_choice_y(words, ytop, y_end_same)

                    out_name = f"{date_key}-{qn:03d}.webp"
                    out_path = ASSETS_DIR / out_name

                    cropped: Optional[Image.Image] = None

                    # ── Pass 1: same column ────────────────────────────────
                    # The visual sits between the LAST line of question text
                    # and the FIRST choice marker. Only worth saving if the
                    # gap is large enough to fit a diagram/table (≥ ~50 PDF
                    # units — more than two text-line heights).
                    if fc_same is not None:
                        below_marker_y = ytop + 14
                        text_bottom = below_marker_y
                        for w in words:
                            wy = float(w["top"])
                            if below_marker_y <= wy < fc_same - 4:
                                if w["text"] and not any(c in CHOICE_MARKERS for c in w["text"]):
                                    text_bottom = max(text_bottom, wy + 12)
                        vy0 = text_bottom
                        vy1 = fc_same - 2
                        # require generous height — text-only questions have ~10 px gap.
                        # 35 catches single-line "다음 자료: 17, 6, ..." bands;
                        # smaller gaps are line spacing, not real figures.
                        if vy1 - vy0 >= 35:
                            band_words = words_in_band(words, vy0, vy1, xl, xh)
                            if band_words <= 4:
                                cropped = crop(page_image(page_index), (xl, vy0, xh, vy1))
                                if cropped and is_mostly_blank(cropped):
                                    cropped = None

                    # ── Pass 2: cross-column overflow (same page, opposite col)
                    # Only when:
                    #   - same column had no choices (fc_same is None), AND
                    #   - marker is in LEFT col near the bottom of the page,
                    #     so the question's body/visual continues on the top
                    #     of the right column.
                    near_page_bottom_p2 = ytop > ph - 150
                    if (
                        cropped is None
                        and is_left
                        and fc_same is None
                        and near_page_bottom_p2
                    ):
                        opp_words = pd["right_words"]
                        opp_spans = pd["right_spans"]
                        opp_xl, opp_xh = column_x_bounds(opp_words, pd["width"], False)
                        cropped = try_overflow_band(
                            page_image(page_index), opp_words, opp_spans,
                            opp_xl, opp_xh, ph, footer_y,
                        )

                    # ── Pass 3: cross-PAGE overflow ──────────────────────
                    # Triggered ONLY when:
                    #  - same-column had no choices (fc_same is None), AND
                    #  - the question marker is in the right (last) column AND
                    #    near the bottom of the page (no room left).
                    near_page_bottom = ytop > ph - 150
                    if (
                        cropped is None
                        and fc_same is None
                        and not is_left
                        and near_page_bottom
                        and page_index + 1 < len(page_data)
                    ):
                        nxt = page_data[page_index + 1]
                        next_words = nxt["left_words"]
                        next_spans = nxt["left_spans"]
                        n_xl, n_xh = column_x_bounds(next_words, nxt["width"], True)
                        cropped = try_overflow_band(
                            page_image(page_index + 1), next_words, next_spans,
                            n_xl, n_xh, nxt["height"], nxt["height"] - FOOTER_RESERVED_Y,
                        )

                    if cropped is not None and try_save(cropped, out_path):
                        saved[qn] = f"assets/questions/{out_name}"

    for img in rendered_cache.values():
        img.close()
    pdf_pdfium.close()
    return saved


def main():
    all_ids = all_question_ids()
    print(f"이미지 추출 대상: 전체 {len(all_ids)}문제 (blank filter로 false positive 거름)")

    by_date: Dict[str, List[int]] = {}
    for qid in all_ids:
        date = qid[:8]
        qn = int(qid[9:])
        by_date.setdefault(date, []).append(qn)

    answer_dir = ROOT / "pdf" / "answers"
    pdf_iter = list(answer_dir.glob("정보처리기사*.pdf")) or list(ROOT.glob("정보처리기사*.pdf"))
    pdfs = {filename_to_date(p.name).replace("-", ""): p for p in pdf_iter}
    if not pdfs:
        print("PDF 파일이 없습니다. pdf/answers/ 폴더를 확인하세요.", file=sys.stderr)
        sys.exit(1)

    # clean output directory
    for old in ASSETS_DIR.glob("*.webp"):
        old.unlink()

    saved_all: Dict[str, str] = {}
    for date_key, qns in by_date.items():
        pdf_path = pdfs.get(date_key)
        if not pdf_path:
            print(f"  ! {date_key} PDF 없음, 건너뜀")
            continue
        print(f"[{date_key}] 처리 중 ({len(qns)}문제)…")
        result = process_pdf(pdf_path, qns)
        for qn, rel in result.items():
            saved_all[f"{date_key}-{qn:03d}"] = rel
        print(f"  → 저장 {len(result)}/{len(qns)}")

    print(f"\n총 저장된 이미지: {len(saved_all)}개")

    for path in (SRC_DATA / "questions.json", PUBLIC_DATA / "questions.json"):
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        attached = 0
        cleared = 0
        for q in data:
            rel = saved_all.get(q["id"])
            if rel:
                q["visual"] = {
                    "type": "image",
                    "src": rel,
                    "alt": f"문제 {q['questionNo']}번 시각 자료",
                }
                attached += 1
                continue
            v = q.get("visual")
            if v and v.get("type") == "image":
                src_rel = v.get("src", "")
                p = ROOT / "public" / src_rel.lstrip("/")
                if not p.exists():
                    q.pop("visual", None)
                    cleared += 1
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {path.name}: visual 첨부 {attached}건 / 정리 {cleared}건")


if __name__ == "__main__":
    main()
