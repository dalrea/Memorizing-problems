export type ChoiceNo = 1 | 2 | 3 | 4;

export interface Choice {
  no: ChoiceNo;
  text: string;
}

export interface Visual {
  type: "html" | "svg" | "image";
  content?: string;
  src?: string;
  alt: string;
}

export interface Question {
  id: string;
  examDate: string;
  roundTitle: string;
  subjectNo: number;
  subjectName: string;
  questionNo: number;
  questionText: string;
  choices: Choice[];
  answer: ChoiceNo;
  explanation: string;
  conceptTags: string[];
  visual?: Visual;
}

export interface NeedsReviewEntry {
  id: string;
  reason: string;
  raw?: unknown;
}

export type AppMode = "quiz" | "review";

export interface AttemptRecord {
  questionId: string;
  totalAttempts: number;
  wrongAttempts: number;
  lastResult: "correct" | "wrong" | null;
  lastAttemptedAt: string | null;
}

export interface UnitProgress {
  examDate: string;
  subjectNo: number;
  completed: boolean;
  stages: number;
  totalAttempts: number;
  finalWrongIds: string[];
  completedAt: string | null;
}

export interface LastLocation {
  mode: AppMode;
  examDate: string;
  subjectNo: number;
  questionId?: string;
}

export interface StudyRecord {
  version: 1;
  exportedAt: string;
  attempts: Record<string, AttemptRecord>;
  units: Record<string, UnitProgress>;
  last?: LastLocation;
}

export const SUBJECTS: { no: number; name: string }[] = [
  { no: 1, name: "소프트웨어 설계" },
  { no: 2, name: "소프트웨어 개발" },
  { no: 3, name: "데이터베이스 구축" },
  { no: 4, name: "프로그래밍 언어 활용" },
  { no: 5, name: "정보시스템 구축관리" },
];

export const subjectNoFromQuestionNo = (qNo: number): number =>
  Math.min(5, Math.max(1, Math.floor((qNo - 1) / 20) + 1));

export const unitKey = (examDate: string, subjectNo: number): string =>
  `${examDate}::S${subjectNo}`;
