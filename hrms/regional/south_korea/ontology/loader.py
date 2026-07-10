# Copyright (c) 2026, Frappe HRMS contributors
# For license information, please see license.txt

"""Graph-as-Markdown ontology loader for the South Korea HRMS.

This module intentionally stays framework-free (no ``frappe`` import at module
scope) so ontology nodes can be parsed without a running bench. Nodes are plain
Markdown files under ``wiki/ontology/{Kind}/{node_id}.md`` with a small YAML-ish
frontmatter block (parsed here without any external dependency such as PyYAML):

	---
	node_id: 근로기준법_제60조
	kind: 법령조항
	label: 연차 유급휴가
	review_state: draft
	sources:
	- 근로기준법 제60조
	---
	본문에서 [[다른노드]] 위키링크는 그래프 엣지가 된다.

HITL gate: ``load_nodes`` returns only ``published`` nodes by default. Draft nodes
are proposals awaiting human (노무사) review and must be requested explicitly.
"""

import dataclasses
import pathlib
import re

WIKILINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")
_REQUIRED_KEYS = ("node_id", "kind", "label", "review_state")


@dataclasses.dataclass
class OntologyNode:
	node_id: str
	kind: str
	label: str
	review_state: str
	sources: list
	body: str
	edges: list
	path: str
	frontmatter: dict  # 원본 frontmatter 전체 (value·effective_year 등 커스텀 키 접근용)


def load_nodes(root, review_state="published"):
	"""Recursively parse ontology nodes under ``root``.

	Args:
		root: directory containing ``{Kind}/{node_id}.md`` files.
		review_state: keep only nodes with this ``review_state`` (default
			``"published"`` — the HITL gate). Pass ``"draft"`` for drafts only,
			or ``None`` to return every node regardless of state.

	Returns:
		``(nodes, errors)`` where ``nodes`` is a list of :class:`OntologyNode`
		and ``errors`` is a list of ``{"path", "error"}`` dicts for files whose
		frontmatter could not be parsed. Missing or empty roots yield ``([], [])``
		without raising.
	"""

	root_path = pathlib.Path(root)
	if not root_path.exists():
		return [], []

	nodes = []
	errors = []
	for path in sorted(root_path.rglob("*.md")):
		text = path.read_text(encoding="utf-8")
		try:
			node = _parse_node(text, path)
		except ValueError as exc:
			errors.append({"path": str(path), "error": str(exc)})
			continue
		if review_state is not None and node.review_state != review_state:
			continue
		nodes.append(node)
	return nodes, errors


def _parse_node(text, path):
	frontmatter, body = _split_frontmatter(text)
	fields = _parse_frontmatter(frontmatter)
	for key in _REQUIRED_KEYS:
		if not fields.get(key):
			raise ValueError(f"frontmatter missing required key: {key}")
	return OntologyNode(
		node_id=fields["node_id"],
		kind=fields["kind"],
		label=fields["label"],
		review_state=fields["review_state"],
		sources=fields.get("sources", []),
		body=body,
		edges=_extract_edges(body),
		path=str(path),
		frontmatter=fields,
	)


def _split_frontmatter(text):
	lines = text.splitlines()
	if not lines or lines[0].strip() != "---":
		raise ValueError("frontmatter block not found (missing opening '---')")
	for index in range(1, len(lines)):
		if lines[index].strip() == "---":
			frontmatter = lines[1:index]
			body = "\n".join(lines[index + 1 :])
			return frontmatter, body
	raise ValueError("frontmatter block not closed (missing closing '---')")


def _parse_frontmatter(lines):
	fields = {}
	current_list_key = None
	for raw in lines:
		if not raw.strip():
			continue
		stripped = raw.strip()
		if stripped.startswith("- ") and current_list_key is not None:
			fields[current_list_key].append(stripped[2:].strip())
			continue
		if ":" not in raw:
			raise ValueError(f"invalid frontmatter line: {raw!r}")
		key, _, value = raw.partition(":")
		key = key.strip()
		value = value.strip()
		if value == "":
			# start of a block list (e.g. ``sources:``)
			fields[key] = []
			current_list_key = key
		else:
			fields[key] = value
			current_list_key = None
	return fields


def _extract_edges(body):
	edges = []
	for match in WIKILINK_PATTERN.findall(body):
		target = match.strip()
		if target and target not in edges:
			edges.append(target)
	return edges


__all__ = ["OntologyNode", "load_nodes"]
