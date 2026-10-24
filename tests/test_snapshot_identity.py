"""Snapshot identity must reflect the exact metadata bytes, without touching live data."""
import ast
import hashlib
import tempfile
import unittest
from pathlib import Path


class SnapshotIdentityTests(unittest.TestCase):
    def test_metadata_contents_change_cache_identity(self):
        source = (Path(__file__).resolve().parents[1] / "app.py").read_text()
        tree = ast.parse(source)
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == "snapshot_identity")
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            metadata = directory / "metadata.json"
            namespace = {"SNAPSHOT_DIR": directory, "hashlib": hashlib}
            exec(compile(ast.Module(body=[function], type_ignores=[]), "app.py", "exec"), namespace)
            metadata.write_text('{"version":1}', encoding="utf-8")
            first = namespace["snapshot_identity"]()
            self.assertEqual(first, hashlib.sha256(metadata.read_bytes()).hexdigest())
            metadata.write_text('{"version":2}', encoding="utf-8")
            second = namespace["snapshot_identity"]()
            self.assertEqual(second, hashlib.sha256(metadata.read_bytes()).hexdigest())
            self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
