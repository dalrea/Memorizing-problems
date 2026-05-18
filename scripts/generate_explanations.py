# -*- coding: utf-8 -*-
"""
Fill empty `explanation` fields with concept-tag-style hints.

We do NOT have a real model here. Instead we attach a short concept hint
derived from keywords in the question text + correct-choice text. The goal is
to make every question useful as a memorization card; the user can refine
explanations later by editing src/data/questions.json directly.
"""

from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "data" / "questions.json"
PUB = ROOT / "public" / "data" / "questions.json"

# Keyword → (tag, snippet) catalogue. Order matters: first match wins.
# Snippets are short, exam-cram style.
CATALOG: list[tuple[str, str, str]] = [
    ("워크.?스루", "워크스루", "워크스루는 명세서를 미리 배포하고 짧은 회의에서 결함을 찾는 비공식 검토. 인스펙션보다 형식성이 낮고 요구사항 오류의 조기 발견이 목적."),
    ("인스펙션|inspection", "인스펙션", "인스펙션은 공식적인 검토 절차로 체크리스트와 역할 분담을 갖고 진행. 결함 데이터로 프로세스 개선에도 활용."),
    ("럼바우|Rumbaugh", "럼바우 분석", "럼바우 분석 절차: 객체 모형(Object) → 동적 모형(Dynamic) → 기능 모형(Functional). '객→동→기' 순."),
    ("스테레오 ?타입|<<", "UML 스테레오타입", "UML 스테레오타입은 길러멧 《 》(이중 꺾쇠) 안에 표기. 확장 모델의 핵심 표기."),
    ("디자인 ?패턴|GoF", "GoF 디자인 패턴", "GoF 패턴은 생성(Builder/Prototype/Singleton 등)·구조(Bridge/Adapter 등)·행위(Visitor/Observer/Strategy 등)로 3분류."),
    ("자료 ?사전|DD\\b", "자료사전", "자료사전 기호: =정의, +구성, [|]선택, { }반복, ( )생략, ** 주석."),
    ("DFD|데이터 ?흐름도", "DFD", "DFD 구성요소: 프로세스·데이터 흐름·데이터 저장소·외부 엔티티. 자료 사전(DD)은 별도 도구."),
    ("HIPO", "HIPO", "HIPO는 하향식 문서화 도구. 가시적·총체적·세부적 도표로 구성되며 보기 쉬움이 특징."),
    ("CASE", "CASE 도구", "CASE는 SW 생명주기 전 단계 지원, 다양한 개발 모형 지원, 그래픽 지원이 핵심. 언어 번역은 컴파일러의 영역."),
    ("응집도|cohesion", "응집도", "응집도(높을수록 좋음): 우연 < 논리 < 시간 < 절차 < 통신 < 순차 < 기능."),
    ("결합도|coupling", "결합도", "결합도(낮을수록 좋음): 자료 < 스탬프 < 제어 < 외부 < 공통 < 내용."),
    ("XP|익스트림", "XP 가치", "XP 5대 가치: 의사소통(Communication)·단순성(Simplicity)·피드백(Feedback)·용기(Courage)·존중(Respect)."),
    ("애자일|agile|스크럼|scrum", "Agile/Scrum", "스크럼: 스프린트(보통 2~4주) 단위 반복. 역할은 PO·SM·개발팀. 데일리 스크럼·스프린트 리뷰·회고가 핵심 이벤트."),
    ("폭포수|waterfall", "폭포수 모형", "폭포수는 순차·단계별 산출물이 명확하나 변경 수용이 어려움."),
    ("나선형|spiral", "나선형 모형", "나선형은 위험분석 중심으로 점진적 개발. 대규모·고위험 프로젝트에 적합."),
    ("프로토타입|prototype", "프로토타입 모형", "프로토타입은 시제품으로 요구사항을 구체화. 사용자 피드백 반영이 빠름."),
    ("COCOMO", "COCOMO", "COCOMO 유형: Organic(5만 라인 이하, 일괄/과학용) · Semi-detached(중간) · Embedded(초대형/실시간)."),
    ("정규화|정규형|1NF|2NF|3NF|BCNF", "정규화", "1NF 원자값 · 2NF 부분 함수 종속 제거 · 3NF 이행 함수 종속 제거 · BCNF 모든 결정자가 후보키."),
    ("이행.?적", "이행 함수 종속", "A→B, B→C이면 A→C. 3NF는 이행 종속을 제거한다."),
    ("외래키|FOREIGN KEY", "외래키 / 참조 무결성", "외래키는 참조 릴레이션의 기본키 값이거나 NULL이어야 한다(참조 무결성)."),
    ("개체 ?무결성", "개체 무결성", "개체 무결성: 기본키는 NULL·중복 불가."),
    ("도메인", "도메인", "도메인은 한 속성이 가질 수 있는 원자값들의 집합."),
    ("뷰|VIEW", "뷰", "뷰는 물리적 저장 없는 가상 테이블. CREATE/DROP, 논리적 독립성 제공, 기본 키 없으면 갱신 제한."),
    ("트랜잭션|ACID", "트랜잭션 ACID", "원자성(Atomicity)·일관성(Consistency)·고립성(Isolation)·지속성(Durability)."),
    ("이항|이상|삽입 ?이상|삭제 ?이상|갱신 ?이상", "이상 현상", "정규화의 목적은 삽입·삭제·갱신 이상 제거."),
    ("SELECT|FROM|WHERE|GROUP BY|HAVING", "SQL", "SELECT는 DML. GROUP BY 후 조건은 HAVING. DISTINCT는 중복 제거."),
    ("DDL", "DDL", "DDL: CREATE·ALTER·DROP·TRUNCATE. UPDATE는 DML."),
    ("DML", "DML", "DML: SELECT·INSERT·UPDATE·DELETE."),
    ("DCL", "DCL", "DCL: GRANT·REVOKE·COMMIT·ROLLBACK."),
    ("스택|stack|LIFO", "스택", "스택은 LIFO 구조. push·pop·top 연산."),
    ("큐|queue|FIFO", "큐", "큐는 FIFO 구조. enqueue·dequeue."),
    ("전위 ?순회|preorder", "전위 순회", "전위 순회는 루트→왼→오. 후위는 왼→오→루트, 중위는 왼→루트→오."),
    ("후위 ?순회|postorder", "후위 순회", "후위 순회는 왼→오→루트."),
    ("중위 ?순회|inorder", "중위 순회", "중위 순회는 왼→루트→오."),
    ("이진 ?탐색|binary ?search", "이진 탐색", "정렬된 배열에서 O(log n). 매 단계마다 탐색 범위를 반으로 줄임."),
    ("버블 ?정렬", "버블 정렬", "버블 정렬은 인접 원소 비교·교환. 평균/최악 O(n²)."),
    ("선택 ?정렬", "선택 정렬", "선택 정렬은 매 패스마다 최솟값을 찾아 앞으로 보냄. O(n²)."),
    ("삽입 ?정렬", "삽입 정렬", "삽입 정렬은 정렬된 부분에 한 원소씩 삽입. 거의 정렬된 데이터에 빠름."),
    ("퀵 ?정렬|quicksort", "퀵 정렬", "퀵 정렬 평균 O(n log n), 최악 O(n²). 분할 정복."),
    ("힙 ?정렬|heap", "힙 정렬", "힙 정렬은 최대힙 구성 후 루트를 반복 추출. O(n log n)."),
    ("합병 ?정렬|머지 ?정렬|merge sort", "합병 정렬", "합병 정렬은 분할 정복으로 O(n log n) 보장. 추가 메모리 필요."),
    ("화이트 ?박스|white ?box", "화이트박스 테스트", "기초 경로(Base Path), 조건/문장/분기 커버리지가 대표 기법. 경계값 분석은 블랙박스."),
    ("블랙 ?박스|black ?box|동치 ?분할|경계값", "블랙박스 테스트", "동치 분할·경계값 분석·원인-결과 그래프 등이 블랙박스."),
    ("알파 ?검사|alpha", "알파 테스트", "개발자 장소에서 통제된 환경에서 사용자가 수행. 베타는 실제 사용 환경."),
    ("베타 ?검사|beta", "베타 테스트", "실제 사용 환경에서 사용자가 단독 수행."),
    ("스텁|stub", "스텁", "하향식 통합에서 하위 모듈 대신 동작하는 임시 모듈."),
    ("드라이버|driver", "드라이버", "상향식 통합에서 상위 모듈 역할을 하는 임시 모듈."),
    ("형상 ?관리|SCM", "형상 관리", "형상 관리는 변경 사항을 식별·통제·감사·기록. 비용/일정 관리와 무관."),
    ("Pareto|파레토", "Pareto 법칙", "오류 80%가 모듈 20%에서 발견 — 80:20 법칙."),
    ("Brooks", "Brooks 법칙", "지연된 SW 프로젝트에 인력 투입은 더 지연을 부른다."),
    ("DRM", "DRM", "DRM 요소: 암호화·키 관리·식별·정책 관리·크랙 방지·인증. 방화벽은 네트워크 보안."),
    ("RSA", "RSA", "RSA는 소인수분해 어려움을 이용한 공개키 암호. 전자서명·키 교환에 사용."),
    ("ECC", "ECC", "ECC는 타원곡선 이산대수 문제 기반. RSA보다 짧은 키로 동등 보안."),
    ("AES|DES|블록 ?암호", "대칭키 블록 암호", "DES 56비트, AES 128/192/256비트. 대칭키는 빠르고 키 분배가 어려움."),
    ("해시|hash|SHA|MD5", "해시 함수", "일방향 해시. 무결성·전자서명. SHA-2/3는 안전, MD5는 충돌 발견됨."),
    ("RIP", "RIP", "RIP는 거리벡터·최대 15홉 제한. 작은 네트워크용."),
    ("OSPF", "OSPF", "OSPF는 링크 상태·다익스트라 기반. 대규모 네트워크용."),
    ("기밀성|무결성|가용성|부인.?방지", "보안 3요소", "기밀성(인가자만 열람)·무결성(인가자만 수정)·가용성(필요 시 접근)·부인방지(행위 부인 불가)."),
    ("키 ?로거|keylogger", "키 로거", "키 입력을 가로채 ID·비밀번호 등을 탈취하는 공격."),
    ("랜섬웨어|ransomware", "랜섬웨어", "파일을 암호화한 뒤 복호화 대가로 금품을 요구하는 악성코드."),
    ("스미싱|smishing", "스미싱", "SMS로 악성 링크를 보내 개인정보·금융정보를 탈취."),
    ("트로이|trojan", "트로이 목마", "정상 프로그램으로 위장한 악성코드. 자가 복제는 하지 않음."),
    ("객체지향|OOP", "객체지향 개념", "캡슐화·상속·다형성·추상화가 핵심 4대 개념."),
    ("캡슐화|encapsulation", "캡슐화", "데이터와 메서드를 묶어 외부에서 직접 접근 못하게 함."),
    ("상속|inheritance", "상속", "상위 클래스의 속성·메서드를 하위 클래스가 물려받음. 코드 재사용."),
    ("다형성|polymorphism", "다형성", "동일 메시지에 다른 객체가 다른 방식으로 응답. 오버로딩/오버라이딩."),
    ("집단화|aggregation|부분.전체", "집단화", "전체-부분 관계(part-whole, is-a-part-of). UML에서 빈 마름모."),
    ("일반화|generalization", "일반화", "공통 속성을 상위 클래스로 추출. is-a 관계."),
    ("UI 원칙|직관성|유효성|학습성", "UI 설계 원칙", "직관성·유효성·학습성·유연성. 누구나 쉽게 이해는 직관성."),
    ("프레임워크|framework", "프레임워크", "재사용 가능한 구조 + 제어 흐름 제공(IoC). 일관성·생산성 향상, 복잡도는 감소가 기대됨."),
    ("미들웨어|middleware", "미들웨어", "RPC·MOM·ORB·TP 모니터·WAS 등. TP 모니터는 트랜잭션 감시·제어."),
    ("HADOOP|하둡|HDFS|맵리듀스", "하둡", "분산 저장(HDFS)+분산 처리(MapReduce). 대용량 비정형 데이터 처리."),
    ("PICONET|블루투스", "피코넷", "블루투스/UWB 기반의 임시 무선 네트워크. 1마스터·다중 슬레이브."),
    ("JSON", "JSON", "키-값 쌍의 경량 데이터 포맷. JavaScript 객체 표기에서 유래."),
    ("프로세스 ?스케줄링|FCFS|SJF|RR|라운드 ?로빈", "스케줄링", "FCFS 도착순, SJF 짧은 작업 우선, RR 시간할당량, SRT 선점형 SJF."),
    ("교착.?상태|deadlock", "교착상태", "4조건: 상호배제·점유와 대기·비선점·환형대기. 모두 충족 시 발생."),
    ("페이지|paging|세그먼트|segment", "메모리 관리", "페이징은 외부 단편화 X·내부 단편화 O. 세그먼테이션은 반대."),
    ("LRU|FIFO|OPT", "페이지 교체", "LRU 가장 오래 사용 안 된 페이지 교체, OPT 미래에 가장 늦게 쓰일 페이지(이상적)."),
    ("TCP|UDP", "TCP/UDP", "TCP 연결지향·신뢰성·흐름제어, UDP 비연결·빠름·비신뢰."),
    ("OSI", "OSI 7계층", "물리·데이터링크·네트워크·전송·세션·표현·응용."),
    ("IP|IPv4|IPv6", "IP 주소", "IPv4 32비트, IPv6 128비트. NAT·DHCP·서브넷 마스크."),
    ("LOC|기능점수|FP", "비용 산정", "LOC=라인수, 노력=라인/생산성·인원. FP는 기능 중심 산정."),
    ("테일러링|tailoring", "테일러링", "내부 기준: 목표·납기·비용·기술환경·구성원 능력. 외부 기준: 법적·국제표준."),
]


def fill_one(q: dict) -> dict:
    if q.get("explanation"):
        return q
    haystack = (q.get("questionText", "") + " " + " ".join(c.get("text", "") for c in q.get("choices", []))).lower()
    tags_added: list[str] = []
    snippets: list[str] = []
    for pattern, tag, snippet in CATALOG:
        if re.search(pattern, haystack, flags=re.IGNORECASE):
            if tag not in tags_added:
                tags_added.append(tag)
                snippets.append(snippet)
            if len(snippets) >= 2:
                break
    if not snippets:
        # generic hint based on correct choice
        ans = q.get("answer")
        correct = next((c.get("text", "") for c in q.get("choices", []) if c.get("no") == ans), "")
        snippets.append(
            f"정답은 {ans}번 '{correct}'. 출제 키워드를 중심으로 개념을 정리하세요."
        )
    q["explanation"] = " ".join(snippets)
    existing_tags = q.get("conceptTags", [])
    for t in tags_added:
        if t not in existing_tags:
            existing_tags.append(t)
    q["conceptTags"] = existing_tags
    return q


def main():
    for path in (
        ROOT / "src" / "data" / "questions.json",
        ROOT / "public" / "data" / "questions.json",
    ):
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for q in data:
            fill_one(q)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"채움: {path}")


if __name__ == "__main__":
    main()
