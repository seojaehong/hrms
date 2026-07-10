# ontology/ — Graph-as-Markdown 온톨로지 (framework-free)

노드는 `wiki/ontology/{Kind}/{node_id}.md`. frontmatter 키는 `node_id/kind/label/review_state/sources`
만 유지(M5 SafeClaw Task/Hazard/Control 통합 대비 단순·범용). 본문 `[[대상노드]]` = 그래프 엣지.

## 재사용 지식 / 함정
- **`@dataclass` 모듈에 `from __future__ import annotations` 금지**. 테스트가
  `importlib.util.spec_from_file_location`으로 로드하는데(모듈을 sys.modules에 등록 안 함),
  future import가 켜지면 애노테이션이 문자열이 되어 dataclass가 `sys.modules[cls.__module__]`을
  조회하다 `NoneType has no attribute __dict__`로 크래시한다. 실제 타입 객체 애노테이션을 쓸 것.
- 모듈 상단 `frappe` import 금지. 인덴트는 **탭**. 파일 IO는 `encoding="utf-8"` 명시.
- PyYAML 등 외부 의존성 가정 금지 — frontmatter 파서는 직접 구현(키:값 + `- 항목` 블록리스트).

## loader.load_nodes 계약
- `load_nodes(root, review_state="published") -> (nodes, errors)`.
- `review_state`: `"published"`(기본, HITL 게이트) | `"draft"` | `None`(전체).
- `OntologyNode`: `node_id, kind, label, review_state, sources(list), body(str), edges(list), path(str)`.
- `errors`: `[{"path": str, "error": str}]` — 불량 frontmatter는 죽지 않고 여기로.
- 없는/빈 루트 → `([], [])` (예외 없음).

## validate.validate_graph 계약
- `validate_graph(nodes) -> [오류 문자열, ...]` (빈 리스트 = 정상 → truthiness 게이트).
- 입력 `nodes`는 loader `OntologyNode` 리스트 또는 동일 필드 duck-type(`node_id/edges/sources/review_state`만 접근).
- 검출 3종: 중복 `node_id`, 고아 엣지(`[[target]]`이 로드된 node_id 집합에 없음), 무출처 `published`(sources 빈 published 금지 — draft는 허용).

## 테스트
`python3 hrms/tests/test_korea_ontology_*.py` 직접 실행. 전체 게이트:
`bash scripts/run_korea_tests.sh ontology`.
