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

    coolant_temp_f: float | None
    intake_temp_f: float | None
    ambient_temp_f: float | None
    oil_temp_f: float | None
    catalyst_temp_b1s1_f: float | None
    catalyst_temp_b1s2_f: float | None
    maf_gps: float | None
    manifold_pressure_kpa: float | None
    module_voltage_v: float | None

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
            "coolant_temp_f": self.coolant_temp_f,
            "intake_temp_f": self.intake_temp_f,
            "ambient_temp_f": self.ambient_temp_f,
            "oil_temp_f": self.oil_temp_f,
            "catalyst_temp_b1s1_f": self.catalyst_temp_b1s1_f,
            "catalyst_temp_b1s2_f": self.catalyst_temp_b1s2_f,
            "maf_gps": self.maf_gps,
            "manifold_pressure_kpa": self.manifold_pressure_kpa,
            "module_voltage_v": self.module_voltage_v,
            "sample_duration_ms": self.sample_duration_ms,
            "sample_rate_hz": self.sample_rate_hz,
            "missing_values": self.missing_values,
            "query_failures": self.query_failures,
            "connection_status": self.connection_status,
        }
