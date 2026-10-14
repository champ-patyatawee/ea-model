#!/usr/bin/env python3
"""Build a bt.py job list for ImpulseBasketEA research runs.

Every job runs the WHOLE 2023.01-2026.10 period at a large deposit so the
equity path is the raw price path (fixed lot => P/L is deposit-independent),
then tools/ibe_report.py turns that one path into ~240 rolling runs.

Usage: python3 tools/mk_ibe_sweep.py <name> <variants.json> > spec.json
"""
import json
import sys

FROM = "2023.01.03"
TO = "2026.10.14"
BIG = 100000

BASE = {
    "InpImpulseRangeATR": "1.5",
    "InpImpulseBodyRatio": "0.50",
    "InpUseClosePos": "true",
    "InpImpulseClosePos": "0.75",
    "InpDirMode": "0",
    "InpBasketTP": "20.0",
    "InpMaxPositions": "8",
    "InpLot": "0.02",
    "InpLotMode": "0",
    "InpCooldownBars": "0",
    "InpMaxEntriesPerDay": "0",
    "InpMinATR": "0.0",
    "InpSameSideOnly": "false",
    "InpNetCapLots": "0.0",
    "InpUseTimeExit": "false",
    "InpCloseBeforeWeekend": "false",
}

# v1.1 base: same behaviour as v1.0 defaults, plus the new levers.
BASE_V11 = {
    "InpImpulseRangeATR": "1.5",
    "InpImpulseBodyRatio": "0.50",
    "InpUseClosePos": "true",
    "InpImpulseClosePos": "0.75",
    "InpDirMode": "0",
    "InpHTF": "0",
    "InpTPMode": "0",
    "InpBasketTP": "20.0",
    "InpTPPerOz": "1.50",
    "InpMaxPositions": "8",
    "InpMaxPosPerDir": "0",
    "InpAllowLong": "true",
    "InpAllowShort": "true",
    "InpSameSideOnly": "false",
    "InpNetCapLots": "0.0",
    "InpAddMinGroupPL": "-1000000",
    "InpUseTimeExit": "false",
    "InpCloseBeforeWeekend": "false",
    "InpUseGroupTrail": "false",
    "InpFlatHour": "-1",
    "InpBlockHourFrom": "-1",
    "InpBlockHourTo": "-1",
    "InpCooldownBars": "0",
    "InpCooldownAfterClose": "0",
    "InpMaxEntriesPerDay": "0",
    "InpMinATR": "0.0",
    "InpLot": "0.02",
    "InpLotMode": "0",
    "InpLogEvery": "M5",
}


def build(prefix, variants, base=None, expert="ImpulseBasketEA_v1.0"):
    jobs = []
    for v in variants:
        v = dict(v)
        tag = v.pop("tag")
        inputs = dict(base or BASE)
        inputs.update(v)
        inputs["InpLogFile"] = "%s_%s.csv" % (prefix, tag)
        jobs.append({
            "label": "%s_%s" % (prefix, tag),
            "expert": expert,
            "from": FROM,
            "to": TO,
            "deposit": BIG,
            "model": 2,
            "inputs": inputs,
        })
    return jobs


if __name__ == "__main__":
    spec = json.load(open(sys.argv[2]))
    expert = sys.argv[3] if len(sys.argv) > 3 else "ImpulseBasketEA_v1.0"
    base = BASE_V11 if expert.endswith("v1.1") else BASE
    print(json.dumps(build(sys.argv[1], spec, base=base, expert=expert), indent=1))
