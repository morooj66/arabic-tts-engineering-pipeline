"""The interactive demo's JavaScript rules must agree with the Python gate on every one- and two-fault combination."""
import itertools, json, shutil, subprocess, unittest
from pathlib import Path
from arabic_tts_pipeline import gate, judge

DEMO = Path(__file__).resolve().parents[1] / "docs" / "interactive-demo"
FAULTS = sorted(judge.FAULTS)

@unittest.skipUnless(shutil.which("node"), "node is not installed")
class InteractiveParity(unittest.TestCase):
    def test_gate_parity(self):
        combos = [()] + [(f,) for f in FAULTS] + list(itertools.combinations(FAULTS, 2))
        script = "const E=require(%s);console.log(JSON.stringify(%s.map(c=>E.gate(c))))" % (json.dumps(str(DEMO / "engine.js")), json.dumps([list(c) for c in combos]))
        js = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
        for combo, got in zip(combos, js):
            ev = judge.MockJudge({"x": list(combo)}).evaluate("x", "نَهْرْ")
            want = gate.evaluate(ev, "نَهْرٌ")
            self.assertEqual((got["status"], got["score"], sorted(got["hard"])), (want.status, want.score, sorted(want.hard)), combo)

    def test_scenarios_use_only_known_faults(self):
        out = subprocess.run(["node", "-e", "const E=require(%s);console.log(JSON.stringify(E.SCENARIOS))" % json.dumps(str(DEMO / "engine.js"))], capture_output=True, text=True, check=True).stdout
        for s in json.loads(out):
            for v in ("voice_a", "voice_b"):
                for at in s.get(v, {}).get("attempts", []): self.assertLessEqual(set(at.get("faults", [])), set(FAULTS))

if __name__ == "__main__": unittest.main()
