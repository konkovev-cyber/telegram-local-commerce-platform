import json
import logging
from app.core.logging import JSONFormatter, trace_id_var


def test_json_formatter():
    formatter = JSONFormatter()
    trace_id_var.set("trace-abc-123")
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)

    assert data["level"] == "INFO"
    assert data["logger"] == "test_logger"
    assert data["message"] == "Test message"
    assert data["trace_id"] == "trace-abc-123"
    assert "timestamp" in data
    assert "module" in data
    assert "line" in data
