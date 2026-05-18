import type { AppContext } from "../app";
import { loadRecord } from "../storage";
import { roundExamDates } from "../utils/progress";
import { roundProgressPercent } from "../utils/progress";
import { formatRoundTitle } from "../utils/date";
import { SUBJECTS } from "../types";
import { backBar } from "./common";

export async function renderHome(ctx: AppContext): Promise<void> {
  const rec = await loadRecord();
  const dates = roundExamDates(ctx.questions);
  const lastBlock = rec.last
    ? `<a class="card resume" href="#/${rec.last.mode}/${rec.last.examDate}/${rec.last.subjectNo}">
        <div class="card-title">이어서 학습</div>
        <div class="card-meta">${formatRoundTitle(rec.last.examDate)} · ${
        SUBJECTS[rec.last.subjectNo - 1].name
      } · ${rec.last.mode === "quiz" ? "암기 훈련" : "해설 읽기"}</div>
      </a>`
    : "";

  ctx.root.innerHTML = `
    ${backBar("정보처리기사 암기장")}
    <main class="page">
      <section class="hero">
        <h1>정보처리기사 암기장</h1>
        <p class="muted">반복해서 외우는 것이 목적입니다. 한 단원 20문제를 모두 맞힐 때까지 반복하세요.</p>
      </section>

      ${lastBlock}

      <section class="grid two">
        <a class="card primary" href="#/select/quiz">
          <div class="card-title">암기 훈련 모드</div>
          <div class="card-meta">틀린 문제만 반복해서 외우기</div>
        </a>
        <a class="card" href="#/select/review">
          <div class="card-title">해설 읽기 모드</div>
          <div class="card-meta">문제 · 정답 · 해설을 한눈에</div>
        </a>
        <a class="card" href="#/mistakes">
          <div class="card-title">자주 틀린 문제</div>
          <div class="card-meta">오답 횟수 순으로 보기</div>
        </a>
        <a class="card" href="#/settings">
          <div class="card-title">백업 · 복원 · 초기화</div>
          <div class="card-meta">학습 기록 JSON</div>
        </a>
      </section>

      <section class="block">
        <h2>회차별 진행률</h2>
        <ul class="round-list">
          ${dates
            .map((d) => {
              const p = roundProgressPercent(ctx.questions, rec, d);
              return `<li>
                <div class="round-line">
                  <span class="round-title">${formatRoundTitle(d)}</span>
                  <span class="round-pct">${p}%</span>
                </div>
                <div class="bar"><span style="width:${p}%"></span></div>
              </li>`;
            })
            .join("")}
        </ul>
      </section>
    </main>`;
}
