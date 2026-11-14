"""Step 3: Yearly hourly PV hosting capacity on the IEEE 34-bus feeder (unity power factor PV).

Usage:
    python hosting_capacity.py                 # PV at bus 848, substation source at 1.03 pu
    python hosting_capacity.py 848 1.05        # same, but IEEE's original 1.05 pu source
    python hosting_capacity.py 848 1.03 250    # coarser 250 kW steps (default is 50 kW)
    python hosting_capacity.py 848 1.03 50 vv  # PV with IEEE 1547-2018 Category B volt-var
    python hosting_capacity.py 848 1.03 50 pf95 # PV at constant 0.95 power factor, absorbing vars
"""
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd
import opendssdirect as dss

here = Path(__file__).parent
PV_BUS = sys.argv[1] if len(sys.argv) > 1 else "848"
# IEEE sets the source at 1.05 pu, a peak-load setting. At light load that alone puts
# bus 814 above 1.05 pu with no PV, so the study uses 1.03 pu (a typical substation setpoint).
SOURCE_PU = float(sys.argv[2]) if len(sys.argv) > 2 else 1.03
V_MAX = 1.05            # ANSI C84.1 Range A upper limit (pu)
THERMAL_MAX = 100.0     # % of normal rating
STEP_KW = int(sys.argv[3]) if len(sys.argv) > 3 else 50
SIZES_KW = range(0, 6001, STEP_KW)   # PV sizes to test (kW AC)
CONTROL = sys.argv[4].lower() if len(sys.argv) > 4 else "unity"   # "unity", "vv" or "pf95"
KVA_RATIO = 1.12        # inverter kVA / kW: room for 44% of kVA as vars at full output (1547 Cat B)
TOL = 1e-4              # ignore round-off: 1.05004 pu still counts as 1.0500 pu

# Conductor ampacities (Kersting, Distribution System Modeling & Analysis, App. A)
# IEEE 34 configs: 300 = 1/0 ACSR, 301 = #2 ACSR, 302/303 = #4 ACSR, 304 = #2 ACSR
LINE_AMPS = {"300": 230, "301": 180, "302": 140, "303": 140, "304": 180}

# ---------- 1. Profiles ----------
load_shape = np.array(open(here / "profiles" / "PaperLoadShape.txt").read().replace(",", " ").split(), float)
pvw = pd.read_csv(here / "profiles" / "pvwatts_hourly.csv", skiprows=31, encoding="utf-8-sig")
pv_shape = pvw["AC System Output (W)"].to_numpy() / (4000 / 1.2)   # 0..1 of inverter AC rating
day_hours = np.flatnonzero(pv_shape > 0)                            # PV can only cause problems in daylight
print(f"PV bus: {PV_BUS}   source: {SOURCE_PU} pu   control: {CONTROL}   daylight hours: {len(day_hours)}")

# ---------- 2. Circuit ----------
dss.Text.Command(f'compile "{here / "34Bus" / "ieee34Mod1.dss"}"')
dss.Text.Command(f"vsource.source.pu={SOURCE_PU}")
for name in dss.Lines.AllNames():
    dss.Lines.Name(name)
    dss.Lines.NormAmps(LINE_AMPS[dss.Lines.LineCode()])
dss.Text.Command(f"new PVSystem.PV1 phases=3 bus1={PV_BUS} kV=24.9 kVA=1 Pmpp=1 "
                 "irradiance=1 pf=1 %cutin=0.1 %cutout=0.1")
if CONTROL == "pf95":
    # IEEE 1547 constant power factor mode: negative pf = PV absorbs vars
    dss.Text.Command("PVSystem.PV1.pf=-0.95")
if CONTROL == "vv":
    # IEEE 1547-2018 Category B default volt-var curve:
    # 0.92 pu -> +44% (supply vars), 0.98-1.02 pu -> 0, 1.08 pu -> -44% (absorb vars)
    dss.Text.Command("new XYcurve.vv1547 npts=6 Xarray=[0.50 0.92 0.98 1.02 1.08 1.50] "
                     "Yarray=[1 1 0 0 -1 -1]")
    dss.Text.Command("new InvControl.vv mode=VOLTVAR vvc_curve1=vv1547 RefReactivePower=VARMAX "
                     "voltage_curvex_ref=rated DERList=[PVSystem.PV1]")
    dss.Text.Command("set maxcontroliter=200")

# Nodes we check for overvoltage: every 24.9 kV and 4.16 kV customer node (not the 69 kV source)
all_nodes = dss.Circuit.AllNodeNames()
check = np.array([not n.startswith("sourcebus") for n in all_nodes])
# Elements we check for overload: lines + the substation and in-line transformers
thermal_elems = [f"Line.{n}" for n in dss.Lines.AllNames()] + ["Transformer.subxf", "Transformer.xfm1"]


def worst_loading():
    """Return (max % loading, element name) over all thermal elements."""
    worst, who = 0.0, ""
    for e in thermal_elems:
        dss.Circuit.SetActiveElement(e)
        amps = dss.CktElement.CurrentsMagAng()[0:2 * dss.CktElement.NumPhases():2]  # terminal 1
        pct = max(amps) / dss.CktElement.NormalAmps() * 100
        if pct > worst:
            worst, who = pct, e
    return worst, who


# ---------- 3. Sweep PV size ----------
rows = []
t0 = time.time()
for size in SIZES_KW:
    dss.PVsystems.Name("PV1")
    kva = max(size, 1) * KVA_RATIO
    dss.Text.Command(f"PVSystem.PV1.kVA={kva} kvarMax={0.44 * kva} kvarMaxAbs={0.44 * kva}")
    dss.PVsystems.Name("PV1")
    dss.PVsystems.Pmpp(max(size, 1e-3))
    vmax, vmax_where, vmax_hour = 0.0, "", -1
    tmax, tmax_where, tmax_hour = 0.0, "", -1
    not_converged = 0
    for h in day_hours:
        dss.Solution.LoadMult(load_shape[h])
        dss.PVsystems.Name("PV1")
        dss.PVsystems.Irradiance(pv_shape[h])
        dss.Solution.Solve()
        not_converged += not dss.Solution.Converged()
        v = np.array(dss.Circuit.AllBusMagPu())[check]
        i = int(v.argmax())
        if v[i] > vmax:
            vmax, vmax_where, vmax_hour = float(v[i]), np.array(all_nodes)[check][i], int(h)
        t, who = worst_loading()
        if t > tmax:
            tmax, tmax_where, tmax_hour = t, who, int(h)
    ok = vmax <= V_MAX + TOL and tmax <= THERMAL_MAX + TOL
    rows.append(dict(pv_kw=size, vmax_pu=round(vmax, 4), vmax_node=vmax_where, vmax_hour=vmax_hour,
                     max_loading_pct=round(tmax, 1), max_loading_elem=tmax_where, tmax_hour=tmax_hour,
                     not_converged=not_converged, pass_=ok))
    print(f"{size:5d} kW  Vmax {vmax:.4f} pu at {vmax_where:7s} (hr {vmax_hour:4d})  "
          f"loading {tmax:5.1f}% {tmax_where:18s}  {'PASS' if ok else 'FAIL'}  nc={not_converged}  [{time.time() - t0:.0f} s]")
    if not ok and size > 0:
        break   # first failing size found; larger sizes will also fail

res = pd.DataFrame(rows)
res.to_csv(here / f"results_step3_hc_bus{PV_BUS}_src{SOURCE_PU}_step{STEP_KW}_{CONTROL}.csv", index=False)
passing = res[res["pass_"]]
hc = int(passing["pv_kw"].max()) if len(passing) else 0
print(f"\nHosting capacity at bus {PV_BUS}, source {SOURCE_PU} pu ({CONTROL}, {STEP_KW} kW steps): {hc} kW")
