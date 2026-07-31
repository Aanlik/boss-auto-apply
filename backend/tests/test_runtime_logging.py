from __future__ import annotations

import logging


def test_runtime_logging_writes_and_rotates_diagnostics(tmp_path):
    from app.services import runtime_logging

    runtime_logging._configured = False
    path = runtime_logging.configure_runtime_logging(tmp_path)
    logging.getLogger("test_runtime").warning("diagnostic marker")

    assert path == tmp_path / "logs" / "runtime.log"
    assert "diagnostic marker" in path.read_text(encoding="utf-8")
