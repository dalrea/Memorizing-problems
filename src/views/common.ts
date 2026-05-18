export function el(html: string): HTMLElement {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild as HTMLElement;
}

export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function renderVisual(v?: {
  type: "html" | "svg" | "image";
  content?: string;
  src?: string;
  alt: string;
}): string {
  if (!v) return "";
  if (v.type === "html" && v.content) return `<div class="visual">${v.content}</div>`;
  if (v.type === "svg" && v.content) return `<div class="visual visual-svg">${v.content}</div>`;
  if (v.type === "image" && v.src)
    return `<div class="visual"><img src="${v.src}" alt="${escapeHtml(v.alt)}" loading="lazy" /></div>`;
  return "";
}

export function backBar(label = "← 홈"): string {
  return `<nav class="topbar"><a href="#/" class="back">${label}</a></nav>`;
}
