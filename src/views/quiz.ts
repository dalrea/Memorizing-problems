import type { AppContext } from "../app";
import { recordAttempt, setLast, setUnitProgress } from "../storage";
import { unitQuestions } from "../utils/progress";
import { SUBJECTS } from "../types";
import type { ChoiceNo, Question } from "../types";
import { formatRoundTitle } from "../utils/date";
import { backBar, escapeHtml, renderVisual } from "./common";

export async function renderQuiz(
  ctx: AppContext,
  examDate: string,
  subjectNo: number
): Promise<void> {
  const all = unitQuestions(ctx.questions, examDate, subjectNo);
  if (all.length === 0) {
    ctx.root.innerHTML = `${backBar()}<main class="page"><h1>문제가 없습니다.</h1></main>`;
    return;
  }
  await setLast({ mode: "quiz", examDate, subjectNo });

  let stage = 1;
  let pool: Question[] = all.slice();
  let idx = 0;
  let totalAttempts = 0;
  let correctInStage = 0;
  let wrongInStage: Question[] = [];
  let stageState: "answering" | "feedback" = "answering";
  let selected: ChoiceNo | null = null;

  const subjectName = SUBJECTS[subjectNo - 1].name;

  const drawCard = () => {
    if (idx >= pool.length) {
      drawStageEnd();
      return;
    }
    const q = pool[idx];
    const remain = pool.length - idx;
    ctx.root.innerHTML = `
      ${backBar("← 단원 선택")}
      <main class="page card-page">
        <div class="quiz-head">
          <div class="quiz-head-line">
            <span class="chip">스테이지 ${stage}</span>
            <span class="chip muted">${formatRoundTitle(examDate)}</span>
            <span class="chip muted">${subjectNo}과목 · ${subjectName}</span>
          </div>
          <div class="quiz-stats">
            <span>남은 ${remain}</span><span class="ok">맞힘 ${correctInStage}</span><span class="warn">틀림 ${wrongInStage.length}</span>
          </div>
        </div>

        <article class="question-card">
          <div class="qno">문제 ${q.questionNo}</div>
          <div class="qtext">${escapeHtml(q.questionText)}</div>
          ${renderVisual(q.visual)}
          <ul class="choices">
            ${q.choices
              .map(
                (c) => `
              <li>
                <button class="choice" data-no="${c.no}">
                  <span class="cno">${c.no}</span>
                  <span class="ctext">${escapeHtml(c.text)}</span>
                </button>
              </li>`
              )
              .join("")}
          </ul>
          <div id="feedback" class="feedback hidden"></div>
          <div class="actions">
            <button id="next" class="btn primary hidden">다음 →</button>
          </div>
        </article>
      </main>`;

    stageState = "answering";
    selected = null;

    const choiceButtons = Array.from(ctx.root.querySelectorAll<HTMLButtonElement>(".choice"));
    choiceButtons.forEach((b) =>
      b.addEventListener("click", () => void onPick(Number(b.dataset.no) as ChoiceNo))
    );

    ctx.root.querySelector<HTMLButtonElement>("#next")!.addEventListener("click", () => {
      if (selected !== null && selected !== pool[idx].answer) {
        wrongInStage.push(pool[idx]);
      } else if (selected !== null) {
        correctInStage += 1;
      }
      idx += 1;
      drawCard();
    });
  };

  const onPick = async (pick: ChoiceNo) => {
    if (stageState !== "answering") return;
    stageState = "feedback";
    selected = pick;
    const q = pool[idx];
    const correct = pick === q.answer;
    totalAttempts += 1;
    await recordAttempt(q.id, correct);

    const buttons = Array.from(ctx.root.querySelectorAll<HTMLButtonElement>(".choice"));
    for (const b of buttons) {
      const n = Number(b.dataset.no) as ChoiceNo;
      b.disabled = true;
      if (n === q.answer) b.classList.add("correct");
      else if (n === pick) b.classList.add("wrong");
    }

    const fb = ctx.root.querySelector<HTMLDivElement>("#feedback")!;
    fb.classList.remove("hidden");
    fb.innerHTML = correct
      ? `<div class="fb ok">정답입니다.</div>
         <div class="explanation"><strong>해설</strong><p>${escapeHtml(q.explanation)}</p></div>`
      : `<div class="fb warn">오답입니다. 정답은 ${q.answer}번.</div>
         <div class="explanation"><strong>해설</strong><p>${escapeHtml(q.explanation)}</p>
         ${q.conceptTags.length ? `<div class="tags">${q.conceptTags.map((t) => `<span class="tag">#${escapeHtml(t)}</span>`).join("")}</div>` : ""}</div>`;

    ctx.root.querySelector<HTMLButtonElement>("#next")!.classList.remove("hidden");
  };

  const drawStageEnd = async () => {
    stage += 1;
    if (wrongInStage.length === 0) {
      await setUnitProgress(examDate, subjectNo, {
        completed: true,
        stages: stage - 1,
        totalAttempts: totalAttempts + (await prevTotal()),
        finalWrongIds: [],
        completedAt: new Date().toISOString(),
      });
      ctx.root.innerHTML = `
        ${backBar("← 단원 선택")}
        <main class="page">
          <h1 class="ok">단원 완료 🎉</h1>
          <p>${formatRoundTitle(examDate)} · ${subjectNo}과목 ${subjectName}</p>
          <ul class="stats">
            <li>소요 스테이지 수: <strong>${stage - 1}</strong></li>
            <li>총 시도 수: <strong>${totalAttempts}</strong></li>
            <li>최종 오답: <strong>없음</strong></li>
          </ul>
          <div class="actions">
            <a class="btn" href="#/select/quiz">다른 단원</a>
            <a class="btn" href="#/">홈</a>
          </div>
        </main>`;
      return;
    }
    // next stage with only wrong ones
    ctx.root.innerHTML = `
      ${backBar()}
      <main class="page">
        <h1>스테이지 ${stage - 1} 종료</h1>
        <p>맞힘 ${correctInStage} / 틀림 ${wrongInStage.length}</p>
        <p>틀린 ${wrongInStage.length}문제만 다시 풉니다.</p>
        <button id="continue" class="btn primary big">스테이지 ${stage} 시작</button>
      </main>`;
    ctx.root.querySelector<HTMLButtonElement>("#continue")!.addEventListener("click", () => {
      pool = wrongInStage.slice();
      wrongInStage = [];
      correctInStage = 0;
      idx = 0;
      drawCard();
    });
  };

  const prevTotal = async (): Promise<number> => 0;

  drawCard();
}
