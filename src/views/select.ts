import type { AppContext } from "../app";
import { loadRecord } from "../storage";
import { roundExamDates, unitProgressPercent } from "../utils/progress";
import { formatRoundTitle } from "../utils/date";
import { SUBJECTS } from "../types";
import { backBar } from "./common";

export async function renderSelect(
  ctx: AppContext,
  mode: "quiz" | "review"
): Promise<void> {
  const rec = await loadRecord();
  const dates = roundExamDates(ctx.questions);
  const initialDate = rec.last?.examDate && dates.includes(rec.last.examDate) ? rec.last.examDate : dates[0];

  ctx.root.innerHTML = `
    ${backBar("← 홈")}
    <main class="page">
      <h1>${mode === "quiz" ? "암기 훈련" : "해설 읽기"} — 회차 · 단원 선택</h1>
      <label class="block">
        <span class="label">회차</span>
        <select id="round-select" class="select">
          ${dates
            .map(
              (d) =>
                `<option value="${d}" ${d === initialDate ? "selected" : ""}>${formatRoundTitle(d)}</option>`
            )
            .join("")}
        </select>
      </label>

      <h2>단원</h2>
      <ul id="subject-list" class="subject-list"></ul>
    </main>`;

  const select = ctx.root.querySelector<HTMLSelectElement>("#round-select")!;
  const list = ctx.root.querySelector<HTMLUListElement>("#subject-list")!;

  const draw = () => {
    const examDate = select.value;
    list.innerHTML = SUBJECTS.map((s) => {
      const p = unitProgressPercent(ctx.questions, rec, examDate, s.no);
      const href = mode === "quiz" ? `#/quiz/${examDate}/${s.no}` : `#/review/${examDate}/${s.no}`;
      return `<li>
        <a class="subject-card" href="${href}">
          <div class="subject-line">
            <span class="subject-no">${s.no}과목</span>
            <span class="subject-name">${s.name}</span>
            ${p.completed ? `<span class="badge ok">완료</span>` : ""}
            ${p.wrongHeavy > 0 ? `<span class="badge warn">오답 ${p.wrongHeavy}</span>` : ""}
          </div>
          <div class="bar"><span style="width:${p.percent}%"></span></div>
        </a>
      </li>`;
    }).join("");
  };

  select.addEventListener("change", draw);
  draw();
}
