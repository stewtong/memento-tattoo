from pathlib import Path
import tomllib

from memento_tattoo import __version__


def test_runtime_version_matches_project_metadata():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == project["project"]["version"]
