export function formatRoundTitle(examDate: string): string {
  const [y, m, d] = examDate.split("-");
  return `${y}년 ${m}월 ${d}일 필기`;
}

export function shortDate(examDate: string): string {
  const [y, m, d] = examDate.split("-");
  return `${y}.${m}.${d}`;
}
