from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from agentcut_director.audit import structural_efficiency_audit
from agentcut_director.cutgraph import CutGraphError, new_project, project_hash, validate_project
from agentcut_director.diffing import semantic_diff
from agentcut_director.identity import CLI_NAME, PRODUCT_NAME, VERSION, product_identity
from agentcut_director.migration import migrate_classic3
from agentcut_director.operations import ConflictError, apply_transaction, preflight, undo_last
from agentcut_director.remotion import BridgeVerificationError, export_remotion_bundle, verify_remotion_bundle


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Director4Tests(unittest.TestCase):
    def make_project(self, root: Path, count: int = 3) -> dict:
        project = new_project("Test", fps=30)
        cursor = 0
        for index in range(count):
            asset_id = f"img-{index+1}"
            path = root / f"{asset_id}.svg"
            path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"><text>{asset_id}</text></svg>', encoding="utf-8")
            project["assets"][asset_id] = {"id": asset_id, "kind": "image", "path": path.name, "sha256": sha(path), "metadata": {}}
            project["timeline"]["scenes"].append({
                "id": f"s{index+1:02d}", "kind": "visual", "start_frame": cursor,
                "duration_frames": 60, "asset_id": asset_id, "motion": {"type": "static"},
            })
            cursor += 60
        project["project"]["duration_frames"] = cursor
        validate_project(project, project_root=root, strict_assets=True)
        return project

    def test_identity_is_distinct_from_classic(self):
        identity = product_identity()
        self.assertEqual(PRODUCT_NAME, "AgentCut Director")
        self.assertEqual(VERSION, "4.0.0")
        self.assertEqual(CLI_NAME, "agentcut-director")
        self.assertIn("Classic", identity["classic_family"])

    def test_hash_is_deterministic(self):
        project = new_project("Hash")
        a = project_hash(project)
        project["history"]["receipts"].append({"volatile": True})
        self.assertEqual(a, project_hash(project))

    def test_atomic_transaction_and_span_impact(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.make_project(Path(temp))
            operations = [{"action": "update_scene", "args": {"scene_id": "s02", "patch": {"motion": {"type": "push", "amount": 0.04}}}}]
            plan = preflight(project, operations)
            self.assertEqual(plan["impact"]["spans"], [[60, 120]])
            updated, receipt = apply_transaction(project, operations, expected_project_hash=project_hash(project))
            self.assertEqual(updated["timeline"]["scenes"][1]["motion"]["type"], "push")
            self.assertEqual(receipt["impact"]["affected_video_frames"], 60)
            self.assertEqual(project["timeline"]["scenes"][1]["motion"]["type"], "static")

    def test_stale_hash_is_rejected(self):
        project = new_project("Conflict")
        with self.assertRaises(ConflictError):
            apply_transaction(project, [{"action": "set_metadata", "args": {"key": "x", "value": 1}}], expected_project_hash="0" * 64)

    def test_failed_batch_does_not_mutate_source(self):
        project = new_project("Atomic")
        original = copy.deepcopy(project)
        with self.assertRaises(CutGraphError):
            apply_transaction(project, [
                {"action": "set_metadata", "args": {"key": "x", "value": 1}},
                {"action": "remove_scene", "args": {"scene_id": "missing"}},
            ])
        self.assertEqual(project, original)

    def test_undo_restores_semantics(self):
        project = new_project("Undo")
        before = project_hash(project)
        updated, _ = apply_transaction(project, [{"action": "set_metadata", "args": {"key": "note", "value": "hello"}}])
        restored, receipt = undo_last(updated)
        self.assertEqual(project_hash(restored), before)
        self.assertTrue(receipt["note"].startswith("undo:"))

    def test_audio_only_impact_avoids_video_render(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = self.make_project(root, 1)
            audio_path = root / "tone.bin"
            audio_path.write_bytes(b"not-real-audio-fixture")
            project["assets"]["aud"] = {"id": "aud", "kind": "audio", "path": audio_path.name, "sha256": sha(audio_path), "metadata": {}}
            op = [{"action": "set_audio_clip", "args": {"audio": {"id": "a1", "asset_id": "aud", "start_frame": 0, "duration_frames": 30, "volume": 0.5}}}]
            plan = preflight(project, op)
            self.assertEqual(plan["impact"]["recommended_action"], "remix_audio_span")
            self.assertEqual(plan["impact"]["affected_video_frames"], 0)

    def test_migration_is_non_destructive(self):
        legacy = {
            "schema": "agentcut.project.v3", "version": "3.3.1",
            "project": {"title": "Legacy", "fps": 30, "width": 1920, "height": 1080},
            "assets": [{"id": "img", "type": "image", "path": "img.png"}],
            "scenes": [{"id": "s1", "start": 0, "duration": 3.0, "asset_id": "img"}],
        }
        original = copy.deepcopy(legacy)
        migrated, warnings = migrate_classic3(legacy)
        self.assertEqual(legacy, original)
        self.assertEqual(migrated["product"]["name"], "AgentCut Director")
        self.assertEqual(migrated["project"]["duration_frames"], 90)
        self.assertEqual(warnings, [])

    def test_remotion_bundle_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = self.make_project(root)
            bundle = root / "bundle"
            export_remotion_bundle(project, project_root=root, output_dir=bundle)
            result = verify_remotion_bundle(bundle, expected_project_hash=project_hash(project))
            self.assertTrue(result["ok"])
            self.assertEqual(result["composition_id"], "AgentCutDirector4")
            manifest = bundle / "public" / "director-manifest.json"
            manifest.write_text(manifest.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaises(BridgeVerificationError):
                verify_remotion_bundle(bundle)

    def test_source_asset_mutation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = self.make_project(root, 1)
            (root / "img-1.svg").write_text("changed", encoding="utf-8")
            with self.assertRaises(CutGraphError):
                export_remotion_bundle(project, project_root=root, output_dir=root / "bundle")

    def test_structural_audit_has_no_billing_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.make_project(Path(temp), 10)
            result = structural_efficiency_audit(project, [{"action": "update_scene", "args": {"scene_id": "s05", "patch": {"motion": {"type": "push"}}}}])
            self.assertGreater(result["context_reduction_ratio"], 0.5)
            self.assertGreater(result["video_frame_reduction_ratio"], 0.8)
            self.assertEqual(result["billing_claim"], "not_measured")

    def test_semantic_diff_matches_items_by_id(self):
        before = {"items": [{"id": "a", "x": 1}, {"id": "b", "x": 2}]}
        after = {"items": [{"id": "b", "x": 3}, {"id": "a", "x": 1}]}
        changes = semantic_diff(before, after)
        self.assertEqual(len(changes), 1)
        self.assertIn("id=b", changes[0]["path"])


if __name__ == "__main__":
    unittest.main()
