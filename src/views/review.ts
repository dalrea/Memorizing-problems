import type { AppContext } from "../app";
import { setLast } from "../storage";
import { unitQuestions } from "../utils/progress";
import { SUBJECTS } from "../types";
import { formatRoundTitle } from "../utils/date";
import { navigate } from "../router";
import { backBar, escapeHtml, renderVisual } from "./common";

export async function renderReview(
  ctx: AppContext,
  examDate: string,
  subjectNo: number,
  questionNo?: number
): Promise<void> {
  const list = unitQuestions(ctx.questions, examDate, subjectNo);
  if (list.length === 0) {
    ctx.root.innerHTML = `${backBar()}<main class="page"><h1>문제가 없습니다.</h1></main>`;
    return;
  }
  await setLast({ mode: "review", examDate, subjectNo });

  let idx = Math.max(0, list.findIndex((q) => q.questionNo === questionNo));
  if (idx < 0) idx = 0;

  const draw = () => {
    const q = list[idx];
    ctx.root.innerHTML = `
      ${backBar("← 단원 선택")}
      <main class="page card-page">
        <div class="quiz-head">
          <div class="quiz-head-line">
            <span class="chip muted">${formatRoundTitle(examDate)}</span>
            <span class="chip muted">${subjectNo}과목 · ${SUBJECTS[subjectNo - 1].name}</span>
            <span class="chip">${idx + 1} / ${list.length}</span>
          </div>
          <label class="jump">
            바로가기
            <select id="jump">
              ${list.map((qq, i) => `<option value="${i}" ${i === idx ? "selected" : ""}>${qq.questionNo}번</option>`).join("")}
            </select>
          </label>
        </div>

        <article class="question-card">
          <div class="qno">문제 ${q.questionNo}</div>
          <div class="qtext">${escapeHtml(q.questionText)}</div>
          ${renderVisual(q.visual)}
          <ul class="choices reveal">
            ${q.choices
              .map(
                (c) => `<li>
                  <div class="choice ${c.no === q.answer ? "correct" : ""}">
                    <span class="cno">${c.no}</span>
                    <span class="ctext">${escapeHtml(c.text)}</span>
                  </div>
                </li>`
              )
              .join("")}
          </ul>
          <div class="explanation">
            <strong>해설</strong>
            <p>${escapeHtml(q.explanation)}</p>
            ${q.conceptTags.length ? `<div class="tags">${q.conceptTags.map((t) => `<span class="tag">#${escapeHtml(t)}</span>`).join("")}</div>` : ""}
          </div>
          <div class="actions row">
            <button class="btn" id="prev" ${idx === 0 ? "disabled" : ""}>← 이전</button>
            <button class="btn primary" id="next" ${idx === list.length - 1 ? "disabled" : ""}>다음 →</button>
          </div>
        </article>
      </main>`;

    ctx.root.querySelector<HTMLButtonElement>("#prev")!.addEventListener("click", () => {
      if (idx > 0) {
        idx -= 1;
        draw();
      }
    });
    ctx.root.querySelector<HTMLButtonElement>("#next")!.addEventListener("click", () => {
      if (idx < list.length - 1) {
        idx += 1;
        draw();
      }
    });
    ctx.root.querySelector<HTMLSelectElement>("#jump")!.addEventListener("change", (e) => {
      idx = Number((e.target as HTMLSelectElement).value);
      navigate({ name: "review", examDate, subjectNo, questionNo: list[idx].questionNo });
    });
  };

  draw();
}
