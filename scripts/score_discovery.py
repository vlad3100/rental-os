#!/usr/bin/env python3
"""Score customer-discovery interviews and apply the ICP decision rules.

Implements docs/01-discovery/icp-scoring-model.md (v0) and the signal classes
from docs/01-discovery/signal-strength-rubric.md. Standard library only.

Usage:
    python3 scripts/score_discovery.py               # score the real tracker
    python3 scripts/score_discovery.py other.csv     # score another file
    python3 scripts/score_discovery.py --demo        # synthetic demo, kept in memory only

Drafted by Claude (AI assistant), 2026-11-08.
"""
from __future__ import annotations

import argparse
import csv
import random
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRACKER = REPO_ROOT / "docs" / "01-discovery" / "interview-tracker.csv"

COLUMNS = [
    "interview_id", "date", "segment", "role", "staff", "lettings_12m",
    "inquiries_last_listing", "hours_last_listing", "hours_source",
    "monthly_tool_spend_eur", "top_step_share_pct", "solved_today",
    "P", "Q", "W", "B", "D", "C", "R", "notes_file",
]
SCORED_SEGMENTS = {"A", "B", "C", "D"}
CONTEXT_SEGMENTS = {"ADJ", "TENANT"}  # inform the synthesis, never score an ICP
HOURS_SOURCES = {"estimate", "records", "observed"}
SYNTHETIC_PREFIX = "SYNTH-"

# dimension -> (weight, max score); see icp-scoring-model.md, section 1
WEIGHTS = {
    "P": (0.25, 3), "C": (0.20, 4), "F": (0.15, 3), "W": (0.15, 3),
    "B": (0.10, 3), "D": (0.10, 3), "R": (0.05, 3),
}
SCORE_MAX = {"P": 3, "Q": 3, "W": 3, "B": 3, "D": 3, "R": 3, "C": 4}
LOW_EVIDENCE_FACTOR = 0.5

MIN_B_INTERVIEWS = 10
MIN_OTHER_SEGMENT = 5


@dataclass
class Interview:
    interview_id: str
    segment: str
    lettings_12m: int
    inquiries: float | None
    hours: float | None
    spend: float | None
    top_step_share: float | None
    solved_today: bool
    scores: dict[str, int]

    @property
    def frequency(self) -> int:
        """F is derived from lettings in the last 12 months, never entered by hand."""
        n = self.lettings_12m
        if n >= 30:
            return 3
        if n >= 10:
            return 2
        if n >= 3:
            return 1
        return 0

    @property
    def fit(self) -> float:
        values = dict(self.scores, F=self.frequency)
        return 100 * sum(w * values[k] / m for k, (w, m) in WEIGHTS.items())

    @property
    def low_evidence(self) -> bool:
        return self.scores["Q"] <= 1

    @property
    def evidence_weighted_fit(self) -> float:
        return self.fit * (LOW_EVIDENCE_FACTOR if self.low_evidence else 1.0)

    @property
    def signal(self) -> str:
        s = self.scores
        if s["P"] == 0 or self.solved_today:
            return "Negative"
        if s["P"] >= 2 and s["Q"] >= 2 and s["C"] >= 3:
            return "Strong"
        if s["P"] >= 2 and s["Q"] >= 1 and s["C"] >= 1:
            return "Medium"
        return "Weak"


@dataclass
class SegmentSummary:
    n: int
    mean_ewf: float
    median_inquiries: float | None
    median_hours: float | None
    median_top_step_share: float | None
    strong_share: float
    commitments_3plus: int
    median_spend: float | None
    low_evidence_share: float


def _optional_number(raw: str | None, field: str, row_id: str, errors: list[str]) -> float | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        errors.append(f"{row_id}: {field} must be a number, got {text!r}")
        return None
    if value < 0:
        errors.append(f"{row_id}: {field} must not be negative")
        return None
    return value


def parse_rows(rows: list[dict[str, str]]) -> tuple[list[Interview], dict[str, int], list[str]]:
    """Validate rows. Returns scored interviews, counts of context interviews, and errors."""
    interviews: list[Interview] = []
    context: dict[str, int] = {}
    errors: list[str] = []
    seen_ids: set[str] = set()

    for line_no, row in enumerate(rows, start=2):
        row_id = (row.get("interview_id") or "").strip() or f"line {line_no}"
        if row_id in seen_ids:
            errors.append(f"{row_id}: duplicate interview_id")
            continue
        seen_ids.add(row_id)

        segment = (row.get("segment") or "").strip().upper()
        if segment in CONTEXT_SEGMENTS:
            context[segment] = context.get(segment, 0) + 1
            continue
        if segment not in SCORED_SEGMENTS:
            errors.append(f"{row_id}: segment must be one of A, B, C, D, ADJ, TENANT; got {segment!r}")
            continue

        row_errors: list[str] = []
        try:
            lettings = int((row.get("lettings_12m") or "").strip())
            if lettings < 0:
                raise ValueError
        except ValueError:
            row_errors.append(f"{row_id}: lettings_12m must be a whole number >= 0")
            lettings = 0

        scores: dict[str, int] = {}
        for key, max_value in SCORE_MAX.items():
            text = (row.get(key) or "").strip()
            try:
                value = int(text)
            except ValueError:
                row_errors.append(f"{row_id}: score {key} is missing or not a whole number")
                continue
            if not 0 <= value <= max_value:
                row_errors.append(f"{row_id}: score {key}={value} is outside 0..{max_value}")
            scores[key] = value

        hours = _optional_number(row.get("hours_last_listing"), "hours_last_listing", row_id, row_errors)
        hours_source = (row.get("hours_source") or "").strip().lower()
        if hours is not None and hours_source not in HOURS_SOURCES:
            row_errors.append(f"{row_id}: hours_source must be estimate, records or observed when hours are given")

        top_step = _optional_number(row.get("top_step_share_pct"), "top_step_share_pct", row_id, row_errors)
        if top_step is not None and top_step > 100:
            row_errors.append(f"{row_id}: top_step_share_pct must be <= 100")

        solved = (row.get("solved_today") or "").strip().lower()
        if solved not in {"", "yes", "no"}:
            row_errors.append(f"{row_id}: solved_today must be yes, no or empty")

        inquiries = _optional_number(row.get("inquiries_last_listing"), "inquiries_last_listing", row_id, row_errors)
        spend = _optional_number(row.get("monthly_tool_spend_eur"), "monthly_tool_spend_eur", row_id, row_errors)

        if row_errors:
            errors.extend(row_errors)
            continue
        interviews.append(Interview(
            interview_id=row_id, segment=segment, lettings_12m=lettings,
            inquiries=inquiries, hours=hours, spend=spend, top_step_share=top_step,
            solved_today=(solved == "yes"), scores=scores,
        ))
    return interviews, context, errors


def _median(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return statistics.median(present) if present else None


def summarise(interviews: list[Interview]) -> dict[str, SegmentSummary]:
    by_segment: dict[str, list[Interview]] = {}
    for item in interviews:
        by_segment.setdefault(item.segment, []).append(item)
    summaries: dict[str, SegmentSummary] = {}
    for segment, items in sorted(by_segment.items()):
        n = len(items)
        summaries[segment] = SegmentSummary(
            n=n,
            mean_ewf=statistics.mean(i.evidence_weighted_fit for i in items),
            median_inquiries=_median([i.inquiries for i in items]),
            median_hours=_median([i.hours for i in items]),
            median_top_step_share=_median([i.top_step_share for i in items]),
            strong_share=sum(i.signal == "Strong" for i in items) / n,
            commitments_3plus=sum(i.scores["C"] >= 3 for i in items),
            median_spend=_median([i.spend for i in items]),
            low_evidence_share=sum(i.low_evidence for i in items) / n,
        )
    return summaries


def decide(summaries: dict[str, SegmentSummary]) -> list[str]:
    """Apply icp-scoring-model.md section 4. Every rule that fires is reported."""
    b = summaries.get("B")
    if b is None or b.n < MIN_B_INTERVIEWS:
        have = 0 if b is None else b.n
        return [f"NOT ENOUGH DATA: {have} of {MIN_B_INTERVIEWS} Segment-B interviews"]
    if b.low_evidence_share > 0.5:
        return [f"NOT ENOUGH DATA: {b.low_evidence_share:.0%} of Segment-B interviews have Q <= 1"]

    fired: list[str] = []
    hours = b.median_hours
    if hours is not None and hours >= 2 and b.strong_share >= 0.30 and b.commitments_3plus >= 3:
        fired.append("KEEP: Segment B and the inquiry-to-viewing wedge meet the thresholds")
    if hours is not None and hours >= 2 and b.median_top_step_share is not None and b.median_top_step_share >= 60:
        fired.append(f"NARROW: median {b.median_top_step_share:.0f}% of time sits in one step; build that step first")
    for segment, s in summaries.items():
        if segment != "B" and s.n >= MIN_OTHER_SEGMENT and s.mean_ewf >= b.mean_ewf + 10:
            fired.append(f"SWITCH: segment {segment} scores {s.mean_ewf:.0f} vs. B {b.mean_ewf:.0f}")
    if hours is not None and hours < 1 and b.strong_share < 0.10:
        fired.append("RETHINK: little time spent and almost no strong signals in Segment B")
    return fired or ["NO RULE FIRED: discuss explicitly in discovery-synthesis.md"]


def demo_rows(seed: int = 7) -> list[dict[str, str]]:
    """Synthetic rows to show how the script works. Never evidence, never written to disk."""
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    for segment, count in (("B", 12), ("C", 5), ("A", 3)):
        for k in range(1, count + 1):
            is_b = segment == "B"
            rows.append({
                "interview_id": f"{SYNTHETIC_PREFIX}{segment}-{k:02d}",
                "date": "2026-01-01", "segment": segment, "role": "owner",
                "staff": str(rng.randint(1, 10)),
                "lettings_12m": str(rng.randint(15, 60) if is_b else rng.randint(1, 8)),
                "inquiries_last_listing": str(rng.randint(40, 400)),
                "hours_last_listing": f"{rng.uniform(0.5, 8):.1f}",
                "hours_source": rng.choice(["estimate", "estimate", "records"]),
                "monthly_tool_spend_eur": str(rng.choice([0, 50, 90, 150])),
                "top_step_share_pct": str(rng.randint(30, 80)),
                "solved_today": rng.choice(["no", "no", "no", "yes"]),
                "P": str(rng.choice([1, 2, 2, 3, 3]) if is_b else rng.choice([0, 1, 2])),
                "Q": str(rng.choice([1, 2, 2, 3])),
                "W": str(rng.randint(0, 3)), "B": str(rng.randint(1, 3)), "D": str(rng.randint(1, 3)),
                "C": str(rng.choice([0, 1, 2, 3, 3, 4]) if is_b else rng.randint(0, 2)),
                "R": str(rng.choice([2, 3])), "notes_file": "",
            })
    return rows


def _fmt(value: float | None, pattern: str = "{:.1f}") -> str:
    return "-" if value is None else pattern.format(value)


def print_report(interviews: list[Interview], summaries: dict[str, SegmentSummary],
                 decisions: list[str], context: dict[str, int], synthetic: bool) -> None:
    if synthetic:
        print("=" * 64)
        print("SYNTHETIC DEMO DATA - NOT EVIDENCE. Do not quote these numbers.")
        print("=" * 64)

    print("\nInterviews")
    print(f"{'id':<16}{'seg':<5}{'F':>3}{'fit':>7}{'ew_fit':>8}  signal")
    for item in sorted(interviews, key=lambda i: i.interview_id):
        print(f"{item.interview_id:<16}{item.segment:<5}{item.frequency:>3}"
              f"{item.fit:>7.1f}{item.evidence_weighted_fit:>8.1f}  {item.signal}")

    print("\nSegments")
    print(f"{'seg':<5}{'n':>3}{'ew_fit':>8}{'inq':>7}{'hours':>7}{'strong':>8}{'C>=3':>6}{'spend':>7}{'lowQ':>6}")
    for segment, s in summaries.items():
        print(f"{segment:<5}{s.n:>3}{s.mean_ewf:>8.1f}{_fmt(s.median_inquiries, '{:.0f}'):>7}"
              f"{_fmt(s.median_hours):>7}{s.strong_share:>8.0%}{s.commitments_3plus:>6}"
              f"{_fmt(s.median_spend, '{:.0f}'):>7}{s.low_evidence_share:>6.0%}")
    if context:
        listed = ", ".join(f"{k}: {v}" for k, v in sorted(context.items()))
        print(f"\nContext interviews (not scored): {listed}")

    print("\nDecision (icp-scoring-model.md, section 4)")
    for line in decisions:
        print(f"- {line}")


def load_tracker(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"tracker is missing columns: {', '.join(missing)}")
        rows = list(reader)
    synthetic = [r["interview_id"] for r in rows if (r.get("interview_id") or "").startswith(SYNTHETIC_PREFIX)]
    if synthetic:
        raise ValueError(f"synthetic rows found in the real tracker ({', '.join(synthetic)}); remove them")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score discovery interviews (Munich Rental Copilot).")
    parser.add_argument("tracker", nargs="?", type=Path, default=DEFAULT_TRACKER,
                        help="interview tracker CSV (default: docs/01-discovery/interview-tracker.csv)")
    parser.add_argument("--demo", action="store_true",
                        help="score synthetic demo rows held in memory instead of a file")
    args = parser.parse_args(argv)

    if args.demo:
        rows = demo_rows()
    else:
        if not args.tracker.exists():
            print(f"error: tracker not found: {args.tracker}", file=sys.stderr)
            return 2
        try:
            rows = load_tracker(args.tracker)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    interviews, context, errors = parse_rows(rows)
    if errors:
        print("Validation errors - fix the tracker and run again:", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1
    if not interviews and not context:
        print("No interviews recorded yet. Add one row per interview to the tracker.")
        return 0

    summaries = summarise(interviews)
    print_report(interviews, summaries, decide(summaries), context, synthetic=args.demo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
