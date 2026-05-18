import type { Question } from "./types";
import { parseHash, navigate } from "./router";
import { renderHome } from "./views/home";
import { renderSelect } from "./views/select";
import { renderQuiz } from "./views/quiz";
import { renderReview } from "./views/review";
import { renderMistakes } from "./views/mistakes";
import { renderSettings } from "./views/settings";

const BASE = (import.meta as any).env?.BASE_URL ?? "/";

export interface AppContext {
  root: HTMLElement;
  questions: Question[];
}

async function loadQuestions(): Promise<Question[]> {
  const url = `${BASE}data/questions.json`.replace(/\/+/g, "/");
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(String(res.status));
    return (await res.json()) as Question[];
  } catch (e) {
    console.error("문제 데이터 로드 실패", e);
    return [];
  }
}

async function route(ctx: AppContext): Promise<void> {
  const r = parseHash(location.hash);
  ctx.root.scrollTo({ top: 0 });
  switch (r.name) {
    case "home":
      await renderHome(ctx);
      break;
    case "select":
      await renderSelect(ctx, r.mode);
      break;
    case "quiz":
      await renderQuiz(ctx, r.examDate, r.subjectNo);
      break;
    case "review":
      await renderReview(ctx, r.examDate, r.subjectNo, r.questionNo);
      break;
    case "mistakes":
      await renderMistakes(ctx);
      break;
    case "settings":
      await renderSettings(ctx);
      break;
  }
}

export async function startApp(root: HTMLElement): Promise<void> {
  const questions = await loadQuestions();
  if (questions.length === 0) {
    root.innerHTML = `
      <main class="page">
        <h1>데이터가 없습니다</h1>
        <p>먼저 <code>npm run extract</code> 로 PDF에서 문제를 추출하세요.</p>
        <p>그 다음 <code>npm run dev</code> 를 다시 실행하면 됩니다.</p>
      </main>`;
    return;
  }
  const ctx: AppContext = { root, questions };
  window.addEventListener("hashchange", () => void route(ctx));
  if (!location.hash) navigate({ name: "home" });
  else await route(ctx);
}
