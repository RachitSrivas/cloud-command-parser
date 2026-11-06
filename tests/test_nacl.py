import subprocess
import sys


def test_nacl_simulation_sample():
    """Verify that network/nacl.json passes 100% on sample packets."""
    cmd = [sys.executable, "tools/nacl_sim.py", "network/nacl.json", "network/packets_sample.jsonl", "--check"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "Correct: 6 / 6 = 100.0%" in res.stdout
