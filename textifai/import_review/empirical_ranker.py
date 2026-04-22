from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EmpiricalPolicy:
    min_samples_for_hard_preference: int = 8
    confidence_weight: float = 0.7
    cold_start_mode: str = "prefer_defaults"
    freshness_half_life_days: float = 21.0


@dataclass(frozen=True)
class EmpiricalEvidence:
    model: str
    samples: int
    weighted_samples: float
    json_valid_rate: float
    stall_rate: float
    subdivision_rate: float
    timeout_rate: float
    avg_latency_seconds: float
    avg_cost_estimate: float
    score: float
    confidence: float


def load_empirical_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return payload.get("records") or []


def append_empirical_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "records": load_empirical_records(path)}
    payload["records"].append(record)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def rank_models_with_evidence(
    *,
    models: list[str],
    phase: str,
    complexity_bucket: str,
    telemetry_path: Path,
    policy: EmpiricalPolicy,
) -> tuple[list[str], list[dict[str, Any]]]:
    evidence_map = build_evidence_map(
        records=load_empirical_records(telemetry_path),
        phase=phase,
        complexity_bucket=complexity_bucket,
        policy=policy,
    )
    ranked = sorted(
        models,
        key=lambda model: (
            evidence_map.get(model, EmpiricalEvidence(model=model, samples=0, weighted_samples=0.0, json_valid_rate=0.0, stall_rate=0.0, subdivision_rate=0.0, timeout_rate=0.0, avg_latency_seconds=0.0, avg_cost_estimate=0.0, score=0.0, confidence=0.0)).score,
            evidence_map.get(model, EmpiricalEvidence(model=model, samples=0, weighted_samples=0.0, json_valid_rate=0.0, stall_rate=0.0, subdivision_rate=0.0, timeout_rate=0.0, avg_latency_seconds=0.0, avg_cost_estimate=0.0, score=0.0, confidence=0.0)).weighted_samples,
        ),
        reverse=True,
    )
    evidence_rows = [asdict(evidence_map[model]) for model in ranked if model in evidence_map]
    return ranked, evidence_rows


def build_evidence_map(
    *,
    records: list[dict[str, Any]],
    phase: str,
    complexity_bucket: str,
    policy: EmpiricalPolicy,
) -> dict[str, EmpiricalEvidence]:
    return _build_evidence_map(
        records=records,
        phase=phase,
        complexity_bucket=complexity_bucket,
        policy=policy,
    )


def make_empirical_record(
    *,
    provider_name: str,
    phase: str,
    complexity_bucket: str,
    model: str,
    success: bool,
    json_valid: bool,
    latency_seconds: float,
    estimated_total_cost: int,
    subdivided: bool = False,
    stalled: bool = False,
    timed_out: bool = False,
) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "provider_name": provider_name,
        "phase": phase,
        "complexity_bucket": complexity_bucket,
        "model": model,
        "success": bool(success),
        "json_valid": bool(json_valid),
        "latency_seconds": round(float(latency_seconds), 4),
        "estimated_total_cost": int(max(0, estimated_total_cost)),
        "subdivided": bool(subdivided),
        "stalled": bool(stalled),
        "timed_out": bool(timed_out),
    }


def _build_evidence_map(
    *,
    records: list[dict[str, Any]],
    phase: str,
    complexity_bucket: str,
    policy: EmpiricalPolicy,
) -> dict[str, EmpiricalEvidence]:
    buckets: dict[str, list[tuple[dict[str, Any], float]]] = {}
    for record in records:
        if str(record.get("phase") or "") != phase:
            continue
        if str(record.get("complexity_bucket") or "") != complexity_bucket:
            continue
        model = str(record.get("model") or "").strip()
        if not model:
            continue
        weight = _freshness_weight(str(record.get("timestamp") or ""), half_life_days=policy.freshness_half_life_days)
        buckets.setdefault(model, []).append((record, weight))
    evidence: dict[str, EmpiricalEvidence] = {}
    for model, weighted_records in buckets.items():
        samples = len(weighted_records)
        weighted_samples = sum(weight for _, weight in weighted_records)
        if weighted_samples <= 0:
            continue
        json_valid_rate = sum((1.0 if rec.get("json_valid") else 0.0) * weight for rec, weight in weighted_records) / weighted_samples
        stall_rate = sum((1.0 if rec.get("stalled") else 0.0) * weight for rec, weight in weighted_records) / weighted_samples
        subdivision_rate = sum((1.0 if rec.get("subdivided") else 0.0) * weight for rec, weight in weighted_records) / weighted_samples
        timeout_rate = sum((1.0 if rec.get("timed_out") else 0.0) * weight for rec, weight in weighted_records) / weighted_samples
        avg_latency_seconds = sum(float(rec.get("latency_seconds") or 0.0) * weight for rec, weight in weighted_records) / weighted_samples
        avg_cost_estimate = sum(float(rec.get("estimated_total_cost") or 0.0) * weight for rec, weight in weighted_records) / weighted_samples
        confidence = min(1.0, weighted_samples / max(1.0, float(policy.min_samples_for_hard_preference)))
        raw_score = (
            (json_valid_rate * 0.55)
            + ((1.0 - stall_rate) * 0.2)
            + ((1.0 - subdivision_rate) * 0.1)
            + ((1.0 - timeout_rate) * 0.1)
            + (1.0 / (1.0 + avg_latency_seconds)) * 0.05
        )
        blended_score = (raw_score * (policy.confidence_weight * confidence)) + (0.5 * (1.0 - (policy.confidence_weight * confidence)))
        evidence[model] = EmpiricalEvidence(
            model=model,
            samples=samples,
            weighted_samples=round(weighted_samples, 4),
            json_valid_rate=round(json_valid_rate, 4),
            stall_rate=round(stall_rate, 4),
            subdivision_rate=round(subdivision_rate, 4),
            timeout_rate=round(timeout_rate, 4),
            avg_latency_seconds=round(avg_latency_seconds, 4),
            avg_cost_estimate=round(avg_cost_estimate, 2),
            score=round(blended_score, 4),
            confidence=round(confidence, 4),
        )
    return evidence


def _freshness_weight(timestamp: str, *, half_life_days: float) -> float:
    if not timestamp:
        return 1.0
    try:
        then = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return 1.0
    now = datetime.now(UTC)
    age_seconds = max(0.0, (now - then.astimezone(UTC)).total_seconds())
    half_life_seconds = max(1.0, half_life_days * 86400.0)
    return math.exp(-math.log(2.0) * age_seconds / half_life_seconds)
