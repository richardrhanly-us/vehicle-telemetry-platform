import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

OPERATORS: dict[str, Callable[[float, float], bool]] = {
    ">": lambda value, threshold: value > threshold,
    ">=": lambda value, threshold: value >= threshold,
    "<": lambda value, threshold: value < threshold,
    "<=": lambda value, threshold: value <= threshold,
    "==": lambda value, threshold: value == threshold,
    "!=": lambda value, threshold: value != threshold,
}


@dataclass(frozen=True)
class AlarmRule:
    name: str
    field: str
    operator: str
    threshold: float
    duration_seconds: float
    severity: str


class AlarmEngine:
    def __init__(self, rules: list[AlarmRule]):
        self.rules = rules
        self._active_since: dict[str, datetime] = {}
        self._triggered: set[str] = set()

    @classmethod
    def from_json_file(cls, path: str | Path) -> "AlarmEngine":
        config_path = Path(path)

        if not config_path.exists():
            return cls([])

        with config_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        rules = []
        for raw_rule in data.get("rules", []):
            operator = raw_rule["operator"]
            if operator not in OPERATORS:
                raise ValueError(f"Unsupported alarm operator: {operator}")

            rules.append(
                AlarmRule(
                    name=raw_rule["name"],
                    field=raw_rule["field"],
                    operator=operator,
                    threshold=float(raw_rule["threshold"]),
                    duration_seconds=float(raw_rule.get("duration_seconds", 0)),
                    severity=raw_rule.get(
                        "severity",
                        "warning",
                    ),
                )
            )

        return cls(rules)

    def evaluate(self, sample: Any) -> list[dict]:
        events = []

        for rule in self.rules:
            value = getattr(sample, rule.field, None)

            if value is None:
                events.extend(
                    self._clear_rule_if_needed(
                        rule,
                        sample,
                        value,
                        reason="value_missing",
                    )
                )
                continue

            condition_met = OPERATORS[rule.operator](
                float(value),
                rule.threshold,
            )

            if condition_met:
                events.extend(
                    self._handle_condition_met(
                        rule,
                        sample,
                        float(value),
                    )
                )
            else:
                events.extend(
                    self._clear_rule_if_needed(
                        rule,
                        sample,
                        float(value),
                        reason="condition_cleared",
                    )
                )

        return events

    def _handle_condition_met(
        self,
        rule: AlarmRule,
        sample: Any,
        value: float,
    ) -> list[dict]:
        timestamp = sample.timestamp

        if rule.name not in self._active_since:
            self._active_since[rule.name] = timestamp

        active_seconds = (timestamp - self._active_since[rule.name]).total_seconds()

        if rule.name not in self._triggered and active_seconds >= rule.duration_seconds:
            self._triggered.add(rule.name)

            return [
                self._build_event(
                    rule=rule,
                    sample=sample,
                    value=value,
                    event_type="triggered",
                    active_seconds=active_seconds,
                )
            ]

        return []

    def _clear_rule_if_needed(
        self,
        rule: AlarmRule,
        sample: Any,
        value: float | None,
        reason: str,
    ) -> list[dict]:
        was_triggered = rule.name in self._triggered
        active_since = self._active_since.pop(
            rule.name,
            None,
        )
        self._triggered.discard(rule.name)

        if not was_triggered:
            return []

        active_seconds = 0.0
        if active_since is not None:
            active_seconds = (sample.timestamp - active_since).total_seconds()

        return [
            self._build_event(
                rule=rule,
                sample=sample,
                value=value,
                event_type="cleared",
                active_seconds=active_seconds,
                reason=reason,
            )
        ]

    def _build_event(
        self,
        rule: AlarmRule,
        sample: Any,
        value: float | None,
        event_type: str,
        active_seconds: float,
        reason: str | None = None,
    ) -> dict:
        event = {
            "type": event_type,
            "timestamp": sample.timestamp.isoformat(),
            "sequence": sample.sequence,
            "rule": rule.name,
            "severity": rule.severity,
            "field": rule.field,
            "operator": rule.operator,
            "threshold": rule.threshold,
            "value": value,
            "duration_seconds": round(
                active_seconds,
                3,
            ),
        }

        if reason is not None:
            event["reason"] = reason

        return event

    def active_alarms(self) -> list[str]:
        return sorted(self._triggered)

    def reset(self) -> None:
        self._active_since.clear()
        self._triggered.clear()
