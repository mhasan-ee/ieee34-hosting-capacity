"""Step 5: Fault study on the IEEE 34-bus feeder, without and with PV at bus 848.

Method
- OpenDSS fault study (bolted 3-phase and 1-phase-to-ground faults at every bus),
  peak load, 1.03 pu source, regulator taps frozen at their peak-load positions.
- PV is inverter-based: its fault current is limited by the inverter electronics.
  We assume 1.2 x rated current (typical 1.1-1.5 x), added to the utility fault
  current (conservative: assumes the two currents are in phase).
- Screens from Arizona Admin. Code R14-2-2615 (same as FERC SGIP fast track):
  PV must not add more than 10% to the maximum fault current, and total DG on the
  circuit should not exceed 15% of the circuit annual peak load.
"""
from pathlib import Path
import math
import pandas as pd
import opendssdirect as dss
import matplotlib.pyplot as plt

here = Path(__file__).parent
PV_BUS = "848"
I_LIMIT = 1.2        # inverter fault current, x rated current (assumption)
KVA_RATIO = 1.12     # same inverter sizing as hosting_capacity.py
CASES = {"Unity PF": 800, "Volt-var": 900, "0.95 PF": 1050}   # kW, from Steps 3-4

# ---------- 1. Fault study without PV ----------
dss.Text.Command(f'compile "{here / "34Bus" / "ieee34Mod1.dss"}"')
dss.Text.Command("vsource.source.pu=1.03")
dss.Solution.Solve()                       # peak load: regulators pick their taps
dss.Text.Command("set controlmode=off")    # freeze taps for the fault study
dss.Text.Command("solve mode=faultstudy")
out_file = here / "_faultstudy_raw.csv"
dss.Text.Command(f'export faultstudy "{out_file}"')
fs = pd.read_csv(out_file)
fs.columns = [c.strip() for c in fs.columns]
fs["Bus"] = fs["Bus"].astype(str).str.strip().str.lower()
out_file.unlink()

# Bus kV and distance from the substation (distance from the IEEE results file)
miles = pd.read_csv(here / "ieee_published" / "ieee34_published_voltages.csv", dtype={"bus": str})
miles = miles.replace({"bus": {"rg10": "814r", "rg11": "852r"}}).groupby("bus")["miles_from_sub"].first()
kv, nph = {}, {}
for b in fs["Bus"]:
    dss.Circuit.SetActiveBus(b)
    kv[b] = round(dss.Bus.kVBase() * math.sqrt(3), 2)    # line-to-line kV
    nph[b] = dss.Bus.NumNodes()                          # 3 = three-phase bus
fs["kV_LL"] = fs["Bus"].map(kv)
fs["phases"] = fs["Bus"].map(nph)
fs["miles"] = fs["Bus"].map(miles)
# Skip the 69 kV source bus and bus 800: the IEEE model makes the source
# artificially stiff ("very stiff" substation transformer), so those values are not physical.
fs = fs[~fs["Bus"].isin(["sourcebus", "800"])].copy()
fs = fs.rename(columns={"3-Phase": "I3ph_noPV_A", "1-Phase": "I1ph_noPV_A", "L-L": "ILL_noPV_A"})

# ---------- 2. PV fault contribution and screens ----------
peak_load_kw = sum((dss.Loads.Name(n), dss.Loads.kW())[1] for n in dss.Loads.AllNames())
i3_pv_bus = float(fs.loc[fs["Bus"] == PV_BUS, "I3ph_noPV_A"].iloc[0])
# PV is 3-phase, so compare with 3-phase faults at 3-phase 24.9 kV buses
weakest = fs[(fs["kV_LL"] == 24.9) & (fs["phases"] == 3)].sort_values("I3ph_noPV_A").iloc[0]

print(f"Feeder peak load (nameplate): {peak_load_kw:.0f} kW  ->  15% screen limit: {0.15 * peak_load_kw:.0f} kW")
print(f"3-phase fault current at PV bus {PV_BUS}: {i3_pv_bus:.1f} A")
print(f"Weakest 3-phase 24.9 kV bus: {weakest['Bus']} ({weakest['I3ph_noPV_A']:.1f} A)\n")
print(f"{'Case':10s} {'PV kW':>6s} {'I_rated A':>9s} {'I_fault A':>9s} {'% at 848':>8s} "
      f"{'% weakest':>9s} {'10% screen':>10s} {'15% screen':>10s}")
summary = []
for case, kw in CASES.items():
    i_rated = kw * KVA_RATIO / (math.sqrt(3) * 24.9)
    i_pv = I_LIMIT * i_rated
    pct_pv_bus = i_pv / i3_pv_bus * 100
    pct_weak = i_pv / weakest["I3ph_noPV_A"] * 100
    s10 = "PASS" if max(pct_pv_bus, pct_weak) <= 10 else "FAIL"
    s15 = "PASS" if kw <= 0.15 * peak_load_kw else "FAIL"
    print(f"{case:10s} {kw:6d} {i_rated:9.1f} {i_pv:9.1f} {pct_pv_bus:7.1f}% {pct_weak:8.1f}% {s10:>10s} {s15:>10s}")
    summary.append(dict(case=case, pv_kw=kw, i_rated_A=round(i_rated, 1), i_pv_fault_A=round(i_pv, 1),
                        pct_of_Isc_at_pv_bus=round(pct_pv_bus, 1), pct_of_Isc_weakest=round(pct_weak, 1),
                        screen_10pct_fault=s10, screen_15pct_peak=s15))
    # Fault current with PV: add the inverter current, scaled by the turns ratio on the 4.16 kV side
    scale = 24.9 / fs["kV_LL"]
    fs[f"I3ph_withPV_{kw}kW_A"] = fs["I3ph_noPV_A"] + i_pv * scale

pd.DataFrame(summary).to_csv(here / "results_step5_screens.csv", index=False)
fs.round(1).to_csv(here / "results_step5_fault_currents.csv", index=False)

# ---------- 3. Key-bus table ----------
key = fs[fs["Bus"].isin(["802", "814", "832", "840", "848", "890"])]
cols = ["Bus", "kV_LL", "miles", "I3ph_noPV_A", "I1ph_noPV_A", f"I3ph_withPV_{max(CASES.values())}kW_A"]
print("\n" + key[cols].round(1).to_string(index=False))

# ---------- 4. Figure: 3-phase fault current vs distance (24.9 kV buses) ----------
m = fs[(fs["kV_LL"] == 24.9) & (fs["phases"] == 3)].sort_values("miles")
kw_max = max(CASES.values())
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.scatter(m["miles"], m["I3ph_noPV_A"], s=60, facecolors="none", edgecolors="#555555",
           linewidths=1.5, label="No PV", zorder=2)
ax.scatter(m["miles"], m[f"I3ph_withPV_{kw_max}kW_A"], s=20, color="#2a6fdb",
           label=f"With {kw_max} kW PV at bus {PV_BUS} (1.2x rated current)", zorder=3)
ax.set_yscale("log")
ax.set_xlabel("Distance from substation (miles)")
ax.set_ylabel("3-phase fault current (A, log scale)")
ax.set_title("IEEE 34-bus 3-phase fault current, 3-phase 24.9 kV buses")
ax.grid(color="#dddddd", linewidth=0.6, which="both")
ax.legend(frameon=False)
fig.tight_layout()
fig.savefig(here / "fig_step5_fault_current.png", dpi=150)
print("\nSaved results_step5_fault_currents.csv, results_step5_screens.csv, fig_step5_fault_current.png")
