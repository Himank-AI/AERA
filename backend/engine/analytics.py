"""Lightweight analytics on live Motor 01 samples. No fabricated points."""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np
from sklearn.ensemble import IsolationForest

KEYS = ("temperature", "current", "vibration", "speed", "voltage", "load", "power")


class MotorAnalytics:
    def __init__(self, window: int = 90) -> None:
        self.window = window
        self.series: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=window))
        self.timestamps: Deque[str] = deque(maxlen=window)
        self.iforest: Optional[IsolationForest] = None
        self.fitted_on = 0
        self.last_score = 0.0

    def reset(self) -> None:
        self.series.clear()
        self.timestamps.clear()
        self.iforest = None
        self.fitted_on = 0
        self.last_score = 0.0

    def push(self, sensors: Dict[str, float], timestamp: str = "") -> None:
        self.timestamps.append(timestamp)
        for key in KEYS:
            if key in sensors:
                self.series[key].append(float(sensors[key]))
        self._maybe_fit()

    def _vector(self, snapshot: Dict[str, float]) -> List[float]:
        return [float(snapshot.get(key, 0.0)) for key in KEYS]

    def _maybe_fit(self) -> None:
        n = len(self.series.get("temperature", []))
        if n < 20:
            return
        if self.iforest is not None and n - self.fitted_on < 20:
            return
        matrix = []
        length = min(len(self.series[key]) for key in KEYS if self.series[key])
        for index in range(length):
            matrix.append([self.series[key][index] for key in KEYS])
        if len(matrix) < 20:
            return
        model = IsolationForest(n_estimators=40, contamination=0.08, random_state=7)
        model.fit(np.array(matrix))
        self.iforest = model
        self.fitted_on = n

    def moving_average(self, key: str, n: int = 8) -> Optional[float]:
        series = list(self.series.get(key, []))
        if not series:
            return None
        take = series[-n:]
        return float(sum(take) / len(take))

    def rate(self, key: str, samples: int = 5) -> float:
        series = list(self.series.get(key, []))
        if len(series) < samples:
            if len(series) < 2:
                return 0.0
            return float(series[-1] - series[0])
        return float(series[-1] - series[-samples])

    def percent_change(self, key: str, samples: int = 8) -> float:
        series = list(self.series.get(key, []))
        if len(series) < samples or abs(series[-samples]) < 1e-6:
            return 0.0
        return 100.0 * (series[-1] - series[-samples]) / abs(series[-samples])

    def zscore(self, key: str, value: float) -> float:
        series = list(self.series.get(key, []))
        if len(series) < 8:
            return 0.0
        # Use earlier window as a local baseline so a developing trend is visible.
        base = series[: max(8, len(series) // 3)]
        mean = float(np.mean(base))
        std = float(np.std(base))
        if std < 1e-6:
            std = 1e-6
        return float((value - mean) / std)

    def isolation_score(self, snapshot: Dict[str, float]) -> float:
        if self.iforest is None:
            return 0.0
        raw = self.iforest.decision_function([self._vector(snapshot)])[0]
        # IsolationForest: lower is more anomalous. Map to 0–1 unusualness.
        score = float(max(0.0, min(1.0, (0.15 - raw) / 0.4)))
        self.last_score = score
        return score

    def trend_map(self, samples: int = 8) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for key in KEYS:
            change = self.percent_change(key, samples)
            if change >= 4:
                out[key] = 1
            elif change <= -4:
                out[key] = -1
            else:
                out[key] = 0
        return out

    def chart_series(self) -> Dict[str, List[Dict[str, float]]]:
        stamps = list(self.timestamps)
        out: Dict[str, List[Dict[str, float]]] = {}
        for key, series in self.series.items():
            values = list(series)
            out[key] = []
            for index, value in enumerate(values):
                stamp = stamps[index] if index < len(stamps) else ""
                out[key].append({"t": stamp, "v": round(value, 3)})
        return out
