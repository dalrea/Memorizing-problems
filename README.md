# 정보처리기사 암기장

정보처리기사 필기 기출문제를 **외우기 위해** 만든 단일 사용자용 정적 학습 사이트입니다.

- 회차 8개 × 100문제 = **800문제**
- Vanilla TypeScript + Vite, React 미사용
- 모바일 우선 디자인
- 학습 기록은 IndexedDB(보조: localStorage)에 저장되며 JSON으로 백업/복원
- 정적 사이트라 GitHub Pages / Netlify / Vercel 어디든 배포 가능

## 두 가지 학습 모드

| 모드 | 설명 |
| --- | --- |
| **암기 훈련** | 회차의 한 단원(20문제)을 풀고, 틀린 문제만 다음 스테이지에서 다시 반복. 20문제를 모두 맞힐 때까지 반복합니다. |
| **해설 읽기** | 문제·정답·해설을 처음부터 한 화면에서 봅니다. 시간이 없을 때 읽기만 하는 용도. |

## 설치

```bash
npm install
# (선택) PDF에서 문제를 다시 추출하려면 Python 3.10+ 가 필요합니다
pip install pdfplumber
```

## 개발 / 빌드

```bash
npm run dev        # 로컬 개발 서버
npm run build      # 정적 사이트 빌드 → dist/
npm run preview    # 빌드 결과 미리보기
npm run validate-data   # questions.json 무결성 검증
```

## PDF에서 데이터 다시 추출

이 저장소에는 이미 추출된 `src/data/questions.json` 과 `public/data/questions.json` 이 포함되어 있습니다. PDF 원본은 저장소에 포함되어 있지 않습니다.

PDF를 갱신했거나 추출을 다시 돌리려면 아래 폴더에 원본을 두세요:

```
pdf/answers/   ← 교사용 PDF (문제 + 본문 정답)
pdf/explains/  ← 해설집 PDF (공식 해설)
```

그런 다음:

```bash
npm run extract                          # 1) 교사용 PDF → questions.json
npm run extract-images                   # 2) 시각 자료 자동 crop (webp)
npm run extract-explanations             # 3) 해설집 PDF → explanation 채움
npm run validate-data                    # 4) 무결성 검증
```

추출 로직:

- 페이지를 좌·우 컬럼으로 분할해 문제 순서를 보존합니다.
- 본문 안의 ❶❷❸❹(채워진 동그라미)를 본문 정답으로 인식하고, 마지막 페이지의 정답표를 **권위 있는 정답**으로 사용합니다.
- 본문 정답과 정답표가 충돌하면 `src/data/needs-review.json` 에 기록됩니다.
- 시각 자료(표/트리/그래프 등)가 의심되는 문제도 같은 파일에 기록됩니다. 해당 문제는 `visual` 필드를 직접 채워 보강하세요.

## 학습 기록 백업 / 복원

홈 화면 → **백업·복원·초기화** 메뉴에서:

- **내보내기**: `jeongcheogi-YYYY-MM-DD.json` 파일로 다운로드
- **가져오기**: JSON 파일을 선택한 후 **병합** 또는 **덮어쓰기** 선택
- **초기화**: 모든 기록 삭제 (2회 확인)

브라우저 저장소는 캐시 정리로 사라질 수 있으므로 가끔 백업해 두세요.

## GitHub Pages 배포

이 저장소를 `main` 브랜치에 푸시하면 `.github/workflows/deploy.yml` 이 자동으로 빌드하여 GitHub Pages에 배포합니다.

저장소 설정에서 한 번만:

1. **Settings → Pages → Source** 를 **GitHub Actions** 로 변경
2. main 브랜치에 push

워크플로우는 `VITE_BASE=/<repo-name>/` 를 자동으로 주입하여 프로젝트 페이지 base path 문제를 처리합니다.

## Netlify / Vercel 배포

루트 도메인으로 배포되므로 base path가 필요 없습니다.

- 빌드 명령: `npm run build`
- 배포 디렉터리: `dist`

## 데이터 구조

```ts
type Question = {
  id: string;                 // ex) "20200606-001"
  examDate: string;           // ex) "2020-06-06"
  roundTitle: string;
  subjectNo: 1 | 2 | 3 | 4 | 5;
  subjectName: string;
  questionNo: number;         // 1~100
  questionText: string;
  choices: { no: 1 | 2 | 3 | 4; text: string }[];
  answer: 1 | 2 | 3 | 4;
  explanation: string;
  conceptTags: string[];
  visual?: {
    type: "html" | "svg" | "image";
    content?: string;         // html/svg 콘텐츠
    src?: string;             // 이미지 경로
    alt: string;
  };
};
```

문제별 시각 자료를 보강하려면 `src/data/questions.json` 과 `public/data/questions.json` 양쪽에서 해당 문제의 `visual` 필드를 채워주세요. 두 파일의 내용은 동일하게 유지되어야 합니다.

## 폴더 구조

```
index.html
vite.config.ts
package.json
src/
  main.ts, app.ts, router.ts, storage.ts, types.ts, styles.css
  views/         home, select, quiz, review, mistakes, settings
  utils/         progress, date, shuffle
  data/          questions.json, needs-review.json
public/
  data/          questions.json, needs-review.json (서빙용 사본)
scripts/
  extract_pdf.py             PDF → JSON
  generate_explanations.py   해설 자동 채움
  validate-data.ts           무결성 검증
.github/workflows/deploy.yml
```
