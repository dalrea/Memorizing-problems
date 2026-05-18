import type { AttemptRecord, LastLocation, StudyRecord, UnitProgress } from "./types";
import { unitKey } from "./types";

const DB_NAME = "jeongcheogi";
const STORE = "kv";
const KEY_RECORD = "record";

let dbPromise: Promise<IDBDatabase> | null = null;

function openDb(): Promise<IDBDatabase> {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE);
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return dbPromise;
}

async function idbGet<T>(key: string): Promise<T | undefined> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const req = tx.objectStore(STORE).get(key);
    req.onsuccess = () => resolve(req.result as T | undefined);
    req.onerror = () => reject(req.error);
  });
}

async function idbSet<T>(key: string, value: T): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put(value, key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

const LS_KEY = "jeongcheogi:record:v1";

function emptyRecord(): StudyRecord {
  return {
    version: 1,
    exportedAt: new Date().toISOString(),
    attempts: {},
    units: {},
  };
}

let cached: StudyRecord | null = null;

export async function loadRecord(): Promise<StudyRecord> {
  if (cached) return cached;
  try {
    const idb = await idbGet<StudyRecord>(KEY_RECORD);
    if (idb && idb.version === 1) {
      cached = idb;
      return cached;
    }
  } catch {
    /* fall through to localStorage */
  }
  const raw = localStorage.getItem(LS_KEY);
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as StudyRecord;
      if (parsed.version === 1) {
        cached = parsed;
        return cached;
      }
    } catch {
      /* ignore */
    }
  }
  cached = emptyRecord();
  return cached;
}

async function persist(): Promise<void> {
  if (!cached) return;
  cached.exportedAt = new Date().toISOString();
  try {
    await idbSet(KEY_RECORD, cached);
  } catch {
    /* IndexedDB unavailable — fall through */
  }
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(cached));
  } catch {
    /* quota — IndexedDB above should still hold data */
  }
}

export async function recordAttempt(
  questionId: string,
  correct: boolean
): Promise<void> {
  const rec = await loadRecord();
  const prev: AttemptRecord = rec.attempts[questionId] ?? {
    questionId,
    totalAttempts: 0,
    wrongAttempts: 0,
    lastResult: null,
    lastAttemptedAt: null,
  };
  prev.totalAttempts += 1;
  if (!correct) prev.wrongAttempts += 1;
  prev.lastResult = correct ? "correct" : "wrong";
  prev.lastAttemptedAt = new Date().toISOString();
  rec.attempts[questionId] = prev;
  await persist();
}

export async function setUnitProgress(
  examDate: string,
  subjectNo: number,
  patch: Partial<UnitProgress>
): Promise<void> {
  const rec = await loadRecord();
  const key = unitKey(examDate, subjectNo);
  const prev: UnitProgress = rec.units[key] ?? {
    examDate,
    subjectNo,
    completed: false,
    stages: 0,
    totalAttempts: 0,
    finalWrongIds: [],
    completedAt: null,
  };
  rec.units[key] = { ...prev, ...patch };
  await persist();
}

export async function getUnitProgress(
  examDate: string,
  subjectNo: number
): Promise<UnitProgress | undefined> {
  const rec = await loadRecord();
  return rec.units[unitKey(examDate, subjectNo)];
}

export async function setLast(loc: LastLocation): Promise<void> {
  const rec = await loadRecord();
  rec.last = loc;
  await persist();
}

export async function exportJson(): Promise<string> {
  const rec = await loadRecord();
  return JSON.stringify(rec, null, 2);
}

export async function importJson(
  text: string,
  mode: "merge" | "overwrite"
): Promise<void> {
  const incoming = JSON.parse(text) as StudyRecord;
  if (incoming.version !== 1) throw new Error("지원하지 않는 백업 버전입니다.");
  if (mode === "overwrite") {
    cached = incoming;
    await persist();
    return;
  }
  const current = await loadRecord();
  for (const [id, a] of Object.entries(incoming.attempts ?? {})) {
    const prev = current.attempts[id];
    if (!prev) {
      current.attempts[id] = a;
      continue;
    }
    current.attempts[id] = {
      questionId: id,
      totalAttempts: prev.totalAttempts + a.totalAttempts,
      wrongAttempts: prev.wrongAttempts + a.wrongAttempts,
      lastResult:
        new Date(a.lastAttemptedAt ?? 0) > new Date(prev.lastAttemptedAt ?? 0)
          ? a.lastResult
          : prev.lastResult,
      lastAttemptedAt:
        new Date(a.lastAttemptedAt ?? 0) > new Date(prev.lastAttemptedAt ?? 0)
          ? a.lastAttemptedAt
          : prev.lastAttemptedAt,
    };
  }
  for (const [k, u] of Object.entries(incoming.units ?? {})) {
    const prev = current.units[k];
    if (!prev) {
      current.units[k] = u;
      continue;
    }
    current.units[k] = {
      ...prev,
      completed: prev.completed || u.completed,
      stages: Math.max(prev.stages, u.stages),
      totalAttempts: prev.totalAttempts + u.totalAttempts,
      finalWrongIds: u.completedAt ? u.finalWrongIds : prev.finalWrongIds,
      completedAt: prev.completedAt ?? u.completedAt,
    };
  }
  if (incoming.last && !current.last) current.last = incoming.last;
  await persist();
}

export async function resetAll(): Promise<void> {
  cached = emptyRecord();
  await persist();
}

export async function getCachedRecord(): Promise<StudyRecord> {
  return loadRecord();
}
