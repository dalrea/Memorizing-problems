export type Route =
  | { name: "home" }
  | { name: "select"; mode: "quiz" | "review" }
  | { name: "quiz"; examDate: string; subjectNo: number }
  | { name: "review"; examDate: string; subjectNo: number; questionNo?: number }
  | { name: "mistakes" }
  | { name: "settings" };

export function parseHash(hash: string): Route {
  const h = hash.replace(/^#\/?/, "");
  if (!h) return { name: "home" };
  const [seg, ...rest] = h.split("/");
  const params = new URLSearchParams(rest.join("/").includes("?") ? rest.join("/").split("?")[1] : "");
  const path = rest.join("/").split("?")[0];
  const parts = path ? path.split("/") : [];
  switch (seg) {
    case "select": {
      const mode = parts[0] === "review" ? "review" : "quiz";
      return { name: "select", mode };
    }
    case "quiz":
      return {
        name: "quiz",
        examDate: parts[0] ?? "",
        subjectNo: Number(parts[1] ?? 1),
      };
    case "review":
      return {
        name: "review",
        examDate: parts[0] ?? "",
        subjectNo: Number(parts[1] ?? 1),
        questionNo: params.get("q") ? Number(params.get("q")) : undefined,
      };
    case "mistakes":
      return { name: "mistakes" };
    case "settings":
      return { name: "settings" };
    default:
      return { name: "home" };
  }
}

export function routeToHash(r: Route): string {
  switch (r.name) {
    case "home":
      return "#/";
    case "select":
      return `#/select/${r.mode}`;
    case "quiz":
      return `#/quiz/${r.examDate}/${r.subjectNo}`;
    case "review": {
      const q = r.questionNo ? `?q=${r.questionNo}` : "";
      return `#/review/${r.examDate}/${r.subjectNo}${q}`;
    }
    case "mistakes":
      return "#/mistakes";
    case "settings":
      return "#/settings";
  }
}

export function navigate(r: Route): void {
  location.hash = routeToHash(r);
}
