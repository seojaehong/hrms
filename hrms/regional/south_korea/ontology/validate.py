# Copyright (c) 2026, Frappe HRMS contributors
# For license information, please see license.txt

"""Graph validator for the South Korea Graph-as-Markdown ontology.

Framework-free (no ``frappe`` import at module scope). Consumes the node list
returned by :func:`loader.load_nodes` and reports structural problems that must
be fixed before nodes are published:

* orphan edges — a ``[[target]]`` wikilink pointing at a node that is not in the
  set of loaded nodes,
* duplicate ``node_id`` — two nodes claiming the same identity,
* published nodes without ``sources`` — no unsourced rule may reach ``published``.

``validate_graph`` returns a plain list of human-readable error strings, empty
when the graph is clean so callers can gate on truthiness.
"""


def validate_graph(nodes):
	"""Return a list of error strings for structural problems in ``nodes``.

	Args:
		nodes: iterable of loader ``OntologyNode`` objects (duck-typed:
			``node_id``, ``edges``, ``sources``, ``review_state``).

	Returns:
		list of human-readable error strings; empty when the graph is valid.
	"""

	nodes = list(nodes)
	errors = []

	known_ids = {node.node_id for node in nodes}

	seen = set()
	for node in nodes:
		if node.node_id in seen:
			errors.append(f"중복 node_id: {node.node_id}")
		else:
			seen.add(node.node_id)

	for node in nodes:
		for target in node.edges:
			if target not in known_ids:
				errors.append(
					f"고아 엣지: {node.node_id} → [[{target}]] (대상 노드 없음)"
				)

	for node in nodes:
		if node.review_state == "published" and not node.sources:
			errors.append(f"무출처 published 노드: {node.node_id} (sources 비어 있음)")

	return errors


__all__ = ["validate_graph"]
