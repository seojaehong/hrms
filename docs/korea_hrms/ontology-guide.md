# 온톨로지 노드 작성 가이드 (Korea HRMS, M2)

> Graph-as-Markdown 지식엔진. 노동법/급여규칙을 Git 버전관리되는 Markdown 노드로 관리하고,
> **에이전트는 `draft` 초안만 제안**하며 `published` 승격은 **사람(노무사)** 만 한다(HITL).
> 배경: `hermes-ontology-north-star.md`, `DEVELOPMENT-MILESTONES.md` M2, `PRD-v2.md` §5.2.

## 1. 디렉터리 구조

```
wiki/ontology/{Kind}/{node_id}.md
```

- `{Kind}` = 노드 종류 디렉터리. 현재 사용: `법령조항`, `급여규칙`. (한글 디렉터리/파일명 OK, 파일은 UTF-8.)
- `{node_id}` = 노드 식별자 = 파일명(확장자 제외). frontmatter의 `node_id`와 일치시킬 것.
- 예: `wiki/ontology/법령조항/근로기준법_제60조.md`, `wiki/ontology/급여규칙/연차_산정.md`.

## 2. frontmatter 스키마

`---` 로 감싼 YAML-ish 블록. 파서는 외부 의존성 없이 직접 구현되어 있으므로
(**PyYAML 가정 금지**) 아래 단순 형식만 지원한다: `키: 값` + `sources:` 다음의 `- 항목` 리스트.

| 키 | 필수 | 설명 |
|----|------|------|
| `node_id` | ✅ | 노드 식별자. 파일명·엣지 참조 대상과 정확히 일치. |
| `kind` | ✅ | 노드 종류(디렉터리명과 동일 개념). 예: `법령조항`, `급여규칙`. |
| `label` | ✅ | 사람이 읽는 제목. |
| `review_state` | ✅ | `draft` 또는 `published`. **에이전트는 `draft`만 생성**. |
| `sources` | (published 필수) | 출처 리스트(`- 항목`). 무출처 `published` 는 검증기가 차단. `draft`도 채우는 것을 권장. |

> **키를 추가하지 말 것.** M5에서 SafeClaw(Task/Hazard/Control) 스키마와 통합할 예정이므로
> frontmatter 키는 위 5종으로 단순·범용 유지한다.

## 3. `[[엣지]]` 규약

본문 안의 `[[대상_node_id]]` 위키링크가 그래프 엣지가 된다.

- 대상은 반드시 **실재하는 노드의 `node_id`** 여야 한다. 없는 대상을 가리키면
  검증기가 "고아 엣지"로 잡는다(3-5절 참조).
- 중복 링크는 로더가 순서 보존·중복 제거해 `edges` 리스트로 만든다.

## 4. 노드 작성법 예시

`wiki/ontology/급여규칙/연차_산정.md`:

```markdown
---
node_id: 연차_산정
kind: 급여규칙
label: 연차 유급휴가 산정
review_state: draft
sources:
- 근로기준법 제60조
---
연차 유급휴가 일수 산정 규칙. 근거 조항은 [[근로기준법_제60조]]이며,
아래 규칙은 `hrms/regional/south_korea/annual_leave.py`의 실제 구현과 일치한다.

## 산정 규칙
- **1년 미만 월개근**: 1개월 개근마다 1일, 상한 11일 (§60②).
- **1년 이상**: 1년간 80% 이상 출근 시 15일 (§60①).
- **3년 이상 가산**: 매 2년당 1일, 총 25일 한도 (§60④).
```

작성 원칙:
- 규칙 서술은 실제 코드(`annual_leave.py`)와 일치시킨다(창작 금지).
- 법령 인용은 원문을 그대로 쓴다(법제처 조회본 등 1차 출처).
- 근거 조항 노드로 `[[...]]` 엣지를 건다.

## 5. draft → published 절차 (HITL)

1. **에이전트**: `review_state: draft` 노드를 초안으로 제안(커밋)한다. **여기까지만.**
2. **노무사(사람)**: 내용을 검토·수정한다.
3. **노무사(사람)**: 승인 시에만 `review_state: draft` → `published` 로 바꿔 커밋한다.

> published 승격은 사람 승인의 산물이다. **에이전트가 `published`로 만들지 말 것.**
> 대중/런타임에는 `published` 노드만 노출되어(`load_nodes(root)` 기본값) 환각 리스크를 차단하고
> 완전한 Audit Trail(법적 컴플라이언스)을 남긴다.

## 6. 로더 · 검증기 · 테스트

**로더** — `hrms/regional/south_korea/ontology/loader.py`
```python
load_nodes(root, review_state="published")  # (nodes, errors)
```
- 기본은 `published`만 반환(HITL 게이트). `review_state="draft"` 는 draft만, `review_state=None` 은 전체.
- 각 노드: `node_id / kind / label / review_state / sources / body / edges / path`.
- 잘못된 frontmatter는 죽지 않고 `errors=[{"path", "error"}]` 로 노출. 없는/빈 루트는 `([], [])`.

**검증기** — `hrms/regional/south_korea/ontology/validate.py`
```python
validate_graph(nodes)  # 오류 문자열 리스트(빈=정상)
```
- 검출: (1) 중복 `node_id`, (2) 고아 엣지(`[[대상]]` 이 노드 집합에 없음), (3) 무출처 `published` 노드.

**테스트/게이트 실행**
```bash
bash scripts/run_korea_tests.sh ontology   # 온톨로지 테스트 + 그래프 검증
bash scripts/run_korea_tests.sh            # 전체 게이트
```
- 게이트는 실 `wiki/ontology` 를 `load_nodes(review_state=None)` 로 로드해 오류·`validate_graph` 를
  모두 확인하고, 문제가 있으면 `exit 1`. `wiki/ontology` 부재/빈 경우도 무해 통과(신규 클론).

## 7. M5 SafeClaw 통합 예고

M5에서 중대재해처벌법 도메인 모듈 **SafeClaw**(Task·Hazard·Control·Article 노드)와 통합한다.
그때 SafeClaw 온톨로지 스키마를 이 M2 형식과 정렬하고(동일 `draft`/`published` HITL),
hrms의 compliance_checklist를 SafeClaw 노드로 매핑한다(중복 구현 금지). 이것이 frontmatter 키를
지금 단순·범용으로 유지하는 이유다.
