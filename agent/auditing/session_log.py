import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

LOG_DIR = Path("logs")


def new_session_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]


def log_event(session_id: str, event_type: str, data: Dict[str, Any]) -> None:
    
    if not session_id:
        return

    LOG_DIR.mkdir(exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "event_type": event_type,
        "data": data,
    }

    log_path = LOG_DIR / f"session_{session_id}.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def read_session(session_id: str) -> list:
    """Reads back every event for a given session, in order."""
    log_path = LOG_DIR / f"session_{session_id}.jsonl"
    if not log_path.is_file():
        return []

    events = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events
