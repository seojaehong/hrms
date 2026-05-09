#!/usr/bin/env python3
"""Direct tests for Korea HRMS Docker runtime source alignment."""

from __future__ import annotations

import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DOCKER_COMPOSE = REPO_ROOT / "docker" / "docker-compose.yml"
INIT_SCRIPT = REPO_ROOT / "docker" / "init.sh"


class KoreaDockerRuntimeSourceTest(unittest.TestCase):
	def test_docker_compose_mounts_this_repo_as_hrms_source(self):
		compose = DOCKER_COMPOSE.read_text(encoding="utf-8")

		self.assertIn("..:/workspace/hrms-source", compose)
		self.assertIn(".:/workspace", compose)

	def test_init_script_installs_hrms_from_mounted_workspace_not_upstream(self):
		init_script = INIT_SCRIPT.read_text(encoding="utf-8")

		self.assertIn("HRMS_APP_SOURCE", init_script)
		self.assertIn("git config --global --add safe.directory \"$HRMS_APP_SOURCE/.git\"", init_script)
		self.assertIn("bench get-app \"$HRMS_APP_SOURCE\"", init_script)
		self.assertNotIn("bench get-app hrms", init_script)
		self.assertIn("exit 1", init_script)

	def test_init_script_validates_mounted_source_before_starting_existing_bench(self):
		init_script = INIT_SCRIPT.read_text(encoding="utf-8")

		validation_index = init_script.index("HRMS_APP_SOURCE does not point to a mounted HRMS workspace")
		existing_bench_index = init_script.index("Bench already exists, skipping init")
		self.assertLess(validation_index, existing_bench_index)

	def test_init_script_keeps_read_only_runtime_boundary(self):
		init_script = INIT_SCRIPT.read_text(encoding="utf-8").lower()

		for forbidden in ("submit", "approve", "send", "provider"):
			self.assertNotIn(forbidden, init_script)


if __name__ == "__main__":
	unittest.main()
