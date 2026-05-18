import type { AppContext } from "../app";
import { loadRecord } from "../storage";
import { topMistakes } from "../utils/progress";
import { SUBJECTS } from "../types";
import { subjectNoFromQuestionNo } from "../types";
import { shortDate } from "../utils/date";
import { backBar, escapeHtml } from "./common";

export async function renderMistakes(ctx: AppContext): Promise<void> {
  const rec = await loadRecord();
  const rows = topMistakes(ctx.questions, rec, 100);

  ctx.root.innerHTML = `
    ${backBar("← 홈")}
    <main class="page">
      <h1>자주 틀린 문제</h1>
      ${rows.length === 0 ? `<p class="muted">아직 기록이 없습니다.</p>` : ""}
      <ul class="mistake-list">
        ${rows
          .map((r) => {
            const sNo = subjectNoFromQuestionNo(r.question.questionNo);
            const sName = SUBJECTS[sNo - 1].name;
            return `<li>
              <a class="mistake-card" href="#/review/${r.question.examDate}/${sNo}?q=${r.question.questionNo}">
                <div class="m-top">
                  <span class="chip warn">오답 ${r.wrongAttempts}회</span>
                  <span class="chip muted">${r.totalAttempts}회 풀이</span>
                </div>
                <div class="m-mid">${shortDate(r.question.examDate)} · ${sName} · ${r.question.questionNo}번</div>
                <div class="m-bot">${escapeHtml(r.question.questionText.slice(0, 80))}…</div>
              </a>
            </li>`;
          })
          .join("")}
      </ul>
    </main>`;
}
