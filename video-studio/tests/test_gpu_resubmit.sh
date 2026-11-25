#!/usr/bin/env bash
# CPU test of vs-gpu run's stalled-submission handling with a fake Kaggle API: the first two submissions stay
# QUEUED, are withdrawn (DeleteKernel) and resubmitted with doubling queue timeouts; the third runs and completes.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"; T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
VS_HOME="$T" KAGGLE_USERNAME=tester python3 - "$HERE/bin/vs-gpu" "$HERE/gpu-jobs/probe.py" "$T/out" <<'PY'
import importlib.machinery, importlib.util, json, sys, time
loader = importlib.machinery.SourceFileLoader("vsgpu", sys.argv[1])
spec = importlib.util.spec_from_loader("vsgpu", loader); m = importlib.util.module_from_spec(spec); loader.exec_module(m)
clock = [0.0]; m.time.time = lambda: clock[0]
def sleep(s): clock[0] += s
m.time.sleep = sleep
calls, subs = [], [0]
def call(service, method, body, timeout=120):
    calls.append(method)
    if method == "GetAcceleratorQuotaStatistics":
        return {"gpuQuota": {"timeUsed": "0s", "totalTimeAllowed": "108000s"}}
    if method == "SaveKernel":
        subs[0] += 1; return {"ref": "/code/tester/vs-probe", "versionNumber": subs[0]}
    if method == "GetKernelSessionStatus":
        return {} if subs[0] < 3 else {"status": "COMPLETE"}       # attempts 1-2 stall, attempt 3 runs
    if method == "ListKernelSessionOutput":
        return {"files": []}
    return {}
m.call = call
sys.argv = ["vs-gpu", "run", sys.argv[2], sys.argv[3], "--queue-timeout", "60", "--resubmits", "4"]
try:
    m.main()
except SystemExit as e:
    code = e.code
print("submissions", subs[0], "deletes", calls.count("DeleteKernel"), "exit", code, "fake minutes", round(clock[0] / 60))
assert subs[0] == 3 and calls.count("DeleteKernel") == 2 and code == 0, calls
PY
echo "PASS vs-gpu run: stalled submissions withdrawn and resubmitted, third one completes"
