import importlib.util
import sys
from pathlib import Path


def load_release_check_module():
    path = Path(__file__).resolve().parents[2] / "scripts" / "release_check.py"
    spec = importlib.util.spec_from_file_location("release_check", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_release_check_uses_the_invoking_python_for_backend_tests():
    release_check = load_release_check_module()

    backend_check = next(check for check in release_check.checks() if check.name == "后端全量测试")

    assert backend_check.command[:3] == [sys.executable, "-m", "pytest"]
    assert backend_check.command[3:] == ["backend/tests", "-q"]
    assert backend_check.env and backend_check.env["PYTHONPATH"].split(":")[0].endswith("/backend")
