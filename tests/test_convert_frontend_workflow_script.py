import subprocess
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PYTHON_BIN = ROOT_DIR / ".venv" / "bin" / "python"


class ConvertFrontendWorkflowScriptTest(unittest.TestCase):
    def test_help_runs_from_repo_root(self) -> None:
        result = subprocess.run(
            [str(PYTHON_BIN), "scripts/convert_frontend_workflow_to_api_json.py", "--help"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Convert a ComfyUI frontend workflow export", result.stdout)
        self.assertIn("--write-local-template", result.stdout)
        self.assertIn("--write-local-bindings", result.stdout)


if __name__ == "__main__":
    unittest.main()
