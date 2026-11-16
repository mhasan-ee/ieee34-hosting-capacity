"""Extra figures for the report:
  fig_report_profiles.png  - input profiles (monthly averages + the limiting day, Apr 2)
  fig_report_v814.png      - yearly maximum voltage at bus 814 vs PV size, per inverter mode
"""
from pathlib import Path
import numpy as np
import pandas as pd
import opendssdirect as dss
import matplotlib.pyplot as plt

here = Path(__file__).parent
load = np.array(open(here / "profiles" / "PaperLoadShape.txt").read().replace(",", " ").split(), float)
pvw = pd.read_csv(here / "profiles" / "pvwatts_hourly.csv", skiprows=31, encoding="utf-8-sig")
pv = pvw["AC System Output (W)"].to_numpy() / (4000 / 1.2)
month = pvw["Month"].to_numpy()
day_hours = np.flatnonzero(pv > 0)
INK, BLUE, ORANGE = "#222222", "#2a6fdb", "#c2410c"

# ---------- Figure A: profiles ----------
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.8))
m = np.arange(1, 13)
a1.plot(m, [load[month == k].mean() for k in m], "o-", color=INK, lw=2, label="Load multiplier (mean)")
a1.plot(m, [pv[month == k].mean() for k in m], "s-", color=BLUE, lw=2, label="PV output, pu of AC rating (mean)")
a1.set_xticks(m, ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
a1.set_ylim(0, 0.8)
a1.set_title("Monthly averages")
a1.legend(frameon=False, fontsize=8, loc="lower center")
a1.grid(color="#dddddd", lw=0.6)
d0 = 91 * 24                                   # Apr 2, hour 0
h = np.arange(24)
a2.plot(h, load[d0:d0 + 24], "o-", color=INK, lw=2, label="Load multiplier")
a2.plot(h, pv[d0:d0 + 24], "s-", color=BLUE, lw=2, label="PV output (pu)")
a2.axvline(12, color=ORANGE, ls="--", lw=1.2)
a2.text(12.4, 0.70, "noon:\nlimiting hour", color=ORANGE, fontsize=8)
a2.set_xticks(range(0, 24, 3))
a2.set_ylim(0, 1.05)
a2.set_xlabel("Hour of day")
a2.set_title("Apr 2 (limiting day)")
a2.legend(frameon=False, fontsize=8, loc="upper left")
a2.grid(color="#dddddd", lw=0.6)
fig.tight_layout()
fig.savefig(here / "fig_report_profiles.png", dpi=200)
print(f"Apr 2 noon: load {load[d0 + 12]:.3f}, PV {pv[d0 + 12]:.3f}")

# ---------- Figure B: max voltage at bus 814 vs PV size ----------
def build(mode):
    dss.Text.Command(f'compile "{here / "34Bus" / "ieee34Mod1.dss"}"')
    dss.Text.Command("vsource.source.pu=1.03")
    dss.Text.Command("new PVSystem.PV1 phases=3 bus1=848 kV=24.9 kVA=1 Pmpp=1 irradiance=1 pf=1 "
                     "%cutin=0.1 %cutout=0.1")
    if mode == "pf95":
        dss.Text.Command("PVSystem.PV1.pf=-0.95")
    if mode == "vv":
        dss.Text.Command("new XYcurve.vv1547 npts=6 Xarray=[0.50 0.92 0.98 1.02 1.08 1.50] Yarray=[1 1 0 0 -1 -1]")
        dss.Text.Command("new InvControl.vv mode=VOLTVAR vvc_curve1=vv1547 RefReactivePower=VARMAX "
                         "voltage_curvex_ref=rated DERList=[PVSystem.PV1]")
        dss.Text.Command("set maxcontroliter=200")


sizes = list(range(0, 1301, 100))
res = {}
for mode in ["unity", "vv", "pf95"]:
    build(mode)
    vmax814 = []
    for size in sizes:
        kva = max(size, 1) * 1.12
        dss.Text.Command(f"PVSystem.PV1.kVA={kva} kvarMax={0.44 * kva} kvarMaxAbs={0.44 * kva}")
        dss.PVsystems.Name("PV1")
        dss.PVsystems.Pmpp(max(size, 1e-3))
        best = 0.0
        for hh in day_hours:
            dss.Solution.LoadMult(load[hh])
            dss.PVsystems.Name("PV1")
            dss.PVsystems.Irradiance(pv[hh])
            dss.Solution.Solve()
            dss.Circuit.SetActiveBus("814")
            best = max(best, max(dss.Bus.puVmagAngle()[0::2]))
        vmax814.append(best)
    res[mode] = vmax814
    print(mode, " ".join(f"{s}:{v:.4f}" for s, v in zip(sizes, vmax814)))

pd.DataFrame({"pv_kw": sizes, **{f"v814_{k}": v for k, v in res.items()}}).round(4).to_csv(
    here / "results_report_v814.csv", index=False)

fig, ax = plt.subplots(figsize=(7.5, 4.2))
style = {"unity": ("o-", INK, "Unity PF"), "vv": ("s-", BLUE, "Volt-var (1547 Cat B)"),
         "pf95": ("^-", ORANGE, "0.95 PF absorbing")}
for k, v in res.items():
    mk, c, lab = style[k]
    ax.plot(sizes, v, mk, color=c, lw=2, ms=5, label=lab)
ax.axhline(1.05, color="#888888", ls="--", lw=1.2)
ax.text(20, 1.0505, "ANSI Range A limit, 1.05 pu", fontsize=8, color="#555555")
ax.set_xlabel("PV size at bus 848 (kW)")
ax.set_ylabel("Yearly max voltage at bus 814 (pu)")
ax.set_title("Bus 814 voltage vs PV size (4,264 daylight hours per point)")
ax.grid(color="#dddddd", lw=0.6)
ax.legend(frameon=False, loc="upper left")
fig.tight_layout()
fig.savefig(here / "fig_report_v814.png", dpi=200)
print("Saved fig_report_profiles.png, fig_report_v814.png, results_report_v814.csv")
