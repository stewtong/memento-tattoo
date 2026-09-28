from pathlib import Path
import tomllib

from memento_tattoo import __version__


def test_runtime_version_matches_project_metadata():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == project["project"]["version"]


def test_cli_reports_its_version():
    import subprocess
    import sys
    proc = subprocess.run([sys.executable, "-m", "memento_tattoo", "--version"], capture_output=True, text=True)
    assert proc.returncode == 0
    assert proc.stdout.strip() == f"memento-tattoo {__version__}"
