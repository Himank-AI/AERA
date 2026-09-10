"""AERA local learning store. Does not replace Motor + HMI history."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from config import DATA_DIR

STORE_PATH = DATA_DIR / "aera_learning.json"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class LearningStore:
    def __init__(self) -> None:
        self.path = STORE_PATH
        self.data = {
            "feedback": [],
            "outcomes": [],
            "incidents": [],
            "expert": [],
            "assessments": [],
        }
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                pass

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, indent=2, default=str))

    def add_feedback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        row = {"id": len(self.data["feedback"]) + 1, "timestamp": _utcnow(), **payload}
        self.data["feedback"].append(row)
        self.save()
        return row

    def add_outcome(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        row = {"id": len(self.data["outcomes"]) + 1, "timestamp": _utcnow(), **payload}
        self.data["outcomes"].append(row)
        self.save()
        return row

    def add_incident(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        row = {"id": len(self.data["incidents"]) + 1, "timestamp": _utcnow(), **payload}
        self.data["incidents"].append(row)
        self.save()
        return row

    def add_expert(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        row = {"id": payload.get("id") or "EXP-OP-{0}".format(len(self.data["expert"]) + 1), **payload}
        self.data["expert"].append(row)
        self.save()
        return row

    def record_assessment(self, payload: Dict[str, Any]) -> None:
        self.data["assessments"].append({"timestamp": _utcnow(), **payload})
        self.data["assessments"] = self.data["assessments"][-400:]
        if len(self.data["assessments"]) % 8 == 0:
            self.save()


learning_store = LearningStore()
