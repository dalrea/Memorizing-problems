import type { Question, StudyRecord } from "../types";
import { subjectNoFromQuestionNo, unitKey } from "../types";

export function unitQuestions(
  all: Question[],
  examDate: string,
  subjectNo: number
): Question[] {
  return all
    .filter((q) => q.examDate === examDate && subjectNoFromQuestionNo(q.questionNo) === subjectNo)
    .sort((a, b) => a.questionNo - b.questionNo);
}

export function roundExamDates(all: Question[]): string[] {
  const set = new Set(all.map((q) => q.examDate));
  return Array.from(set).sort();
}

export function unitProgressPercent(
  all: Question[],
  record: StudyRecord,
  examDate: string,
  subjectNo: number
): { percent: number; completed: boolean; wrongHeavy: number } {
  const qs = unitQuestions(all, examDate, subjectNo);
  if (qs.length === 0) return { percent: 0, completed: false, wrongHeavy: 0 };
  const u = record.units[unitKey(examDate, subjectNo)];
  let touched = 0;
  let wrongHeavy = 0;
  for (const q of qs) {
    const a = record.attempts[q.id];
    if (a && a.totalAttempts > 0) touched += 1;
    if (a && a.wrongAttempts >= 2) wrongHeavy += 1;
  }
  const completed = !!u?.completed;
  const percent = completed ? 100 : Math.round((touched / qs.length) * 100);
  return { percent, completed, wrongHeavy };
}

export function roundProgressPercent(
  all: Question[],
  record: StudyRecord,
  examDate: string
): number {
  let sum = 0;
  for (let s = 1; s <= 5; s++) {
    sum += unitProgressPercent(all, record, examDate, s).percent;
  }
  return Math.round(sum / 5);
}

export interface MistakeRow {
  question: Question;
  wrongAttempts: number;
  totalAttempts: number;
}

export function topMistakes(
  all: Question[],
  record: StudyRecord,
  limit = 50
): MistakeRow[] {
  const rows: MistakeRow[] = [];
  for (const q of all) {
    const a = record.attempts[q.id];
    if (a && a.wrongAttempts > 0) {
      rows.push({ question: q, wrongAttempts: a.wrongAttempts, totalAttempts: a.totalAttempts });
    }
  }
  rows.sort((a, b) => b.wrongAttempts - a.wrongAttempts || b.totalAttempts - a.totalAttempts);
  return rows.slice(0, limit);
}
