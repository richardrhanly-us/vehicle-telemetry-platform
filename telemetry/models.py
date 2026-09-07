from dataclasses import dataclass
from datetime import datetime


@dataclass
class VehicleInfo:
    vin: str | None
    year: str | None
    make: str | None
    model: str | None


@dataclass
class TelemetrySample:
    sequence: int
    timestamp: datetime

    rpm: int | None
    speed_mph: float | None
    throttle_pct: float | None
    load_pct: float | None

    sample_duration_ms: float
    sample_rate_hz: float | None
    missing_values: int
    query_failures: int
    connection_status: str

    def to_dict(self):
        return {
            "sequence": self.sequence,
            "timestamp": self.timestamp.isoformat(),
            "rpm": self.rpm,
            "speed_mph": self.speed_mph,
            "throttle_pct": self.throttle_pct,
            "load_pct": self.load_pct,
            "sample_duration_ms": self.sample_duration_ms,
            "sample_rate_hz": self.sample_rate_hz,
            "missing_values": self.missing_values,
            "query_failures": self.query_failures,
            "connection_status": self.connection_status,
        }