import type { AppContext } from "../app";
import { exportJson, importJson, resetAll } from "../storage";
import { backBar } from "./common";

export async function renderSettings(ctx: AppContext): Promise<void> {
  ctx.root.innerHTML = `
    ${backBar("← 홈")}
    <main class="page">
      <h1>백업 · 복원 · 초기화</h1>

      <section class="block">
        <h2>내보내기</h2>
        <p class="muted">학습 기록을 JSON 파일로 저장합니다. 브라우저 데이터가 사라져도 다시 가져올 수 있습니다.</p>
        <button id="export" class="btn primary">JSON 내보내기</button>
      </section>

      <section class="block">
        <h2>가져오기</h2>
        <p class="muted">기존 기록과 병합하거나 덮어쓸 수 있습니다.</p>
        <input id="import-file" type="file" accept="application/json" />
        <div class="actions row">
          <button id="import-merge" class="btn" disabled>병합으로 가져오기</button>
          <button id="import-overwrite" class="btn warn-btn" disabled>덮어쓰기로 가져오기</button>
        </div>
        <p id="import-msg" class="muted small"></p>
      </section>

      <section class="block">
        <h2>초기화</h2>
        <p class="muted">모든 학습 기록을 삭제합니다. 되돌릴 수 없습니다.</p>
        <button id="reset" class="btn warn-btn">전체 초기화</button>
      </section>
    </main>`;

  ctx.root.querySelector<HTMLButtonElement>("#export")!.addEventListener("click", async () => {
    const text = await exportJson();
    const blob = new Blob([text], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `jeongcheogi-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  });

  const fileInput = ctx.root.querySelector<HTMLInputElement>("#import-file")!;
  const mergeBtn = ctx.root.querySelector<HTMLButtonElement>("#import-merge")!;
  const overwriteBtn = ctx.root.querySelector<HTMLButtonElement>("#import-overwrite")!;
  const msg = ctx.root.querySelector<HTMLParagraphElement>("#import-msg")!;
  let pending: string | null = null;

  fileInput.addEventListener("change", async () => {
    const f = fileInput.files?.[0];
    if (!f) {
      mergeBtn.disabled = true;
      overwriteBtn.disabled = true;
      pending = null;
      msg.textContent = "";
      return;
    }
    pending = await f.text();
    mergeBtn.disabled = false;
    overwriteBtn.disabled = false;
    msg.textContent = `${f.name} 선택됨. 가져오기 방식을 선택하세요.`;
  });

  const doImport = async (mode: "merge" | "overwrite") => {
    if (!pending) return;
    if (mode === "overwrite" && !confirm("덮어쓰면 기존 학습 기록이 사라집니다. 계속하시겠습니까?")) return;
    try {
      await importJson(pending, mode);
      msg.textContent = "가져오기 완료. 홈으로 돌아가세요.";
    } catch (e) {
      msg.textContent = "실패: " + (e as Error).message;
    }
  };
  mergeBtn.addEventListener("click", () => void doImport("merge"));
  overwriteBtn.addEventListener("click", () => void doImport("overwrite"));

  ctx.root.querySelector<HTMLButtonElement>("#reset")!.addEventListener("click", async () => {
    if (!confirm("정말 모든 학습 기록을 삭제할까요? 되돌릴 수 없습니다.")) return;
    if (!confirm("한 번 더 확인합니다. 정말 초기화할까요?")) return;
    await resetAll();
    alert("초기화되었습니다.");
    location.hash = "#/";
  });
}
