"""Batch-level repeated-error monitor. Two modes, and the difference is the lesson of the project:
 * strict   - any tripped rule STOPS production (the original behaviour: it stopped a run every few batches even when the isolated clips were legitimate variation of a voice).
 * advisory - quality rules are recorded and printed after every batch but never stop production; ONLY technical/budget/data-integrity problems stop. Detection and isolation are unchanged, so nothing is hidden: every isolated clip is kept for the human review.
Thresholds are illustrative."""
from dataclasses import dataclass
from collections import Counter

RULES = {"R1_audible_tanween": 2, "R2_isolated_share": 0.40, "R2_min_words": 8, "R3_same_class_words": 3, "R3_share": 0.5, "R4_each_batch": 2, "R4_cumulative": 4}

@dataclass(frozen=True)
class BatchReport:
    batch_id: str
    voice: str
    words: int
    isolated: int
    tanween_clips: int
    classes: dict
    technical_errors: int = 0

@dataclass(frozen=True)
class GuardDecision:
    stop: bool
    advisories: tuple[str, ...]
    line: str

class Guard:
    def __init__(self, mode: str = "advisory"):
        if mode not in {"advisory", "strict"}: raise ValueError(mode)
        self.mode, self.history = mode, []

    def check(self, r: BatchReport) -> GuardDecision:
        trips = []
        if r.tanween_clips >= RULES["R1_audible_tanween"]: trips.append("R1")
        if r.words >= RULES["R2_min_words"] and r.isolated / r.words >= RULES["R2_isolated_share"]: trips.append("R2")
        non_unknown = Counter({c: n for c, n in r.classes.items() if c != "UNKNOWN"})
        if any(n >= RULES["R3_same_class_words"] and n / max(r.isolated, 1) >= RULES["R3_share"] for n in non_unknown.values()): trips.append("R3")
        prev = next((h for h in reversed(self.history) if h.voice == r.voice), None)          # compare a batch only with the previous batch of the SAME voice
        if prev and any(n >= RULES["R4_each_batch"] and prev.classes.get(c, 0) >= RULES["R4_each_batch"] and n + prev.classes[c] >= RULES["R4_cumulative"] for c, n in non_unknown.items()): trips.append("R4")
        self.history.append(r)
        stop = r.technical_errors > 0 or (self.mode == "strict" and bool(trips))
        level = "STOP" if stop else ("ATTENTION" if trips else "OK")
        line = f"GUARD [{level}] {r.batch_id} ({r.voice}): isolated {r.isolated}/{r.words}; classes {dict(r.classes)}; advisories {trips or 'none'}; technical errors {r.technical_errors}"
        return GuardDecision(stop, tuple(trips), line)
