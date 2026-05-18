import { readFileSync } from "node:fs";
import { resolve } from "node:path";

interface Choice {
  no: 1 | 2 | 3 | 4;
  text: string;
}
interface Question {
  id: string;
  examDate: string;
  subjectNo: number;
  questionNo: number;
  questionText: string;
  choices: Choice[];
  answer: 1 | 2 | 3 | 4;
  explanation: string;
}

const file = resolve(process.cwd(), "src/data/questions.json");
const data = JSON.parse(readFileSync(file, "utf-8")) as Question[];

const errors: string[] = [];
const warnings: string[] = [];

const idSet = new Set<string>();
const byRound = new Map<string, Question[]>();

for (const q of data) {
  if (idSet.has(q.id)) errors.push(`중복 id: ${q.id}`);
  idSet.add(q.id);

  if (!q.choices || q.choices.length !== 4)
    errors.push(`${q.id}: 보기 4개가 아님 (${q.choices?.length ?? 0})`);
  for (const n of [1, 2, 3, 4] as const) {
    if (!q.choices?.find((c) => c.no === n))
      errors.push(`${q.id}: 보기 번호 ${n} 누락`);
  }

  if (!([1, 2, 3, 4] as number[]).includes(q.answer))
    errors.push(`${q.id}: answer가 1~4가 아님 (${q.answer})`);

  const expected = Math.min(5, Math.max(1, Math.floor((q.questionNo - 1) / 20) + 1));
  if (q.subjectNo !== expected)
    errors.push(`${q.id}: subjectNo(${q.subjectNo}) ≠ 기대값(${expected})`);

  if (!q.explanation || q.explanation.trim().length === 0)
    warnings.push(`${q.id}: 해설이 비어 있음`);

  const arr = byRound.get(q.examDate) ?? [];
  arr.push(q);
  byRound.set(q.examDate, arr);
}

for (const [date, qs] of byRound) {
  if (qs.length !== 100) errors.push(`${date}: 100문제가 아님 (${qs.length})`);
  const nums = new Set(qs.map((q) => q.questionNo));
  if (nums.size !== 100) errors.push(`${date}: questionNo 중복 또는 누락`);
}

console.log(`총 ${data.length}문제, ${byRound.size}회차`);
if (warnings.length) {
  console.log(`\n경고 ${warnings.length}건 (해설 비어있음 등):`);
  for (const w of warnings.slice(0, 20)) console.log("  -", w);
  if (warnings.length > 20) console.log(`  ... 외 ${warnings.length - 20}건`);
}
if (errors.length) {
  console.error(`\n에러 ${errors.length}건:`);
  for (const e of errors) console.error("  -", e);
  process.exit(1);
}
console.log("\n검증 통과 ✓");
