#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Regression tests for install.py's symlink install/prune/uninstall logic."""

import importlib.util
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


install = load_module("jacob_install", REPO_ROOT / "install.py")


class InstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        # resolve() because macOS /var is a symlink to /private/var and
        # install.py compares resolved paths
        root = Path(self.temp_dir.name).resolve()
        self.skills = root / "repo" / "skills"
        self.target_a = root / "agents-skills"
        self.target_b = root / "claude-skills"
        self.skills.mkdir(parents=True)
        self._orig_skills = install.SKILLS  # pyright: ignore[reportAttributeAccessIssue]
        self._orig_roots = install.TARGET_ROOTS  # pyright: ignore[reportAttributeAccessIssue]
        install.SKILLS = self.skills  # pyright: ignore[reportAttributeAccessIssue]
        install.TARGET_ROOTS = [self.target_a, self.target_b]  # pyright: ignore[reportAttributeAccessIssue]

    def tearDown(self) -> None:
        install.SKILLS = self._orig_skills  # pyright: ignore[reportAttributeAccessIssue]
        install.TARGET_ROOTS = self._orig_roots  # pyright: ignore[reportAttributeAccessIssue]
        self.temp_dir.cleanup()

    def make_skill(self, name: str) -> Path:
        skill_dir = self.skills / name
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: x\n---\nbody\n", encoding="utf-8"
        )
        return skill_dir

    def run_install(self, dry_run: bool = False, force: bool = False) -> int:
        with redirect_stdout(StringIO()):
            return install.install(dry_run, force)

    def test_install_links_every_skill_into_every_root(self) -> None:
        skill = self.make_skill("alpha")
        self.assertEqual(self.run_install(), 0)
        for root in (self.target_a, self.target_b):
            link = root / "alpha"
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), skill)

    def test_foreign_symlink_is_a_conflict_without_force(self) -> None:
        self.make_skill("alpha")
        elsewhere = Path(self.temp_dir.name).resolve() / "elsewhere"
        elsewhere.mkdir()
        self.target_a.mkdir(parents=True)
        (self.target_a / "alpha").symlink_to(elsewhere)
        self.assertEqual(self.run_install(), 1)
        self.assertEqual((self.target_a / "alpha").resolve(), elsewhere)

    def test_force_replaces_foreign_symlink(self) -> None:
        skill = self.make_skill("alpha")
        elsewhere = Path(self.temp_dir.name).resolve() / "elsewhere"
        elsewhere.mkdir()
        self.target_a.mkdir(parents=True)
        (self.target_a / "alpha").symlink_to(elsewhere)
        self.assertEqual(self.run_install(force=True), 0)
        self.assertEqual((self.target_a / "alpha").resolve(), skill)

    def test_force_never_deletes_a_real_directory(self) -> None:
        self.make_skill("alpha")
        self.target_a.mkdir(parents=True)
        real = self.target_a / "alpha"
        real.mkdir()
        (real / "keep.txt").write_text("data", encoding="utf-8")
        self.assertEqual(self.run_install(force=True), 1)
        self.assertTrue((real / "keep.txt").is_file())

    def test_removed_skill_link_is_pruned_on_install(self) -> None:
        self.make_skill("alpha")
        gone = self.make_skill("gone")
        self.assertEqual(self.run_install(), 0)
        (gone / "SKILL.md").unlink()
        gone.rmdir()
        self.assertEqual(self.run_install(), 0)
        for root in (self.target_a, self.target_b):
            self.assertFalse((root / "gone").is_symlink())
            self.assertTrue((root / "alpha").is_symlink())

    def test_uninstall_removes_only_links_into_this_repo(self) -> None:
        self.make_skill("alpha")
        self.assertEqual(self.run_install(), 0)
        elsewhere = Path(self.temp_dir.name).resolve() / "elsewhere"
        elsewhere.mkdir()
        foreign = self.target_a / "foreign"
        foreign.symlink_to(elsewhere)
        with redirect_stdout(StringIO()):
            self.assertEqual(install.uninstall(dry_run=False), 0)
        self.assertFalse((self.target_a / "alpha").is_symlink())
        self.assertTrue(foreign.is_symlink())


if __name__ == "__main__":
    unittest.main()
