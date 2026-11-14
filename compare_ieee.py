"""Step 2: Compare the OpenDSS IEEE 34-bus power flow with IEEE's published results."""
from pathlib import Path
import opendssdirect as dss
import pandas as pd
import matplotlib.pyplot as plt
import sys

here = Path(__file__).parent

# Run "python compare_ieee.py ieee" to lock the regulator taps at IEEE's published positions.
use_ieee_taps = len(sys.argv) > 1 and sys.argv[1].lower() == "ieee"
IEEE_TAPS = {"reg1a": 12, "reg1b": 5, "reg1c": 5, "reg2a": 13, "reg2b": 11, "reg2c": 12}
tag = "ieee_taps" if use_ieee_taps else "auto_taps"

# 1. Solve the base case (same as run_powerflow.py)
dss.Text.Command(f'compile "{here / "34Bus" / "ieee34Mod1.dss"}"')
if use_ieee_taps:
    for reg, tap in IEEE_TAPS.items():
        dss.Text.Command(f"transformer.{reg}.wdg=2 tap={1 + 0.00625 * tap}")
    dss.Text.Command("set controlmode=off")   # stop OpenDSS from moving the taps
dss.Solution.Solve()
print("Case:     ", tag)
print("Converged:", dss.Solution.Converged())

# Totals vs IEEE published (2042.872 kW, 290.258 kvar, 273.049 kW losses)
p, q = dss.Circuit.TotalPower()
loss_kw = dss.Circuit.Losses()[0] / 1000
for name, mine, ieee in [("Source kW", -p, 2042.872), ("Source kvar", -q, 290.258), ("Losses kW", loss_kw, 273.049)]:
    print(f"{name:12s} {mine:8.1f}  IEEE {ieee:8.1f}  diff {(mine - ieee) / ieee * 100:+.2f} %")

# 2. Load IEEE's published voltages
pub = pd.read_csv(here / "ieee_published" / "ieee34_published_voltages.csv", dtype={"bus": str})

# IEEE names the regulator outputs RG10 / RG11; OpenDSS calls them 814r / 852r.
# XF10 (in-line transformer node) has no separate bus in OpenDSS, so we skip it.
name_map = {"rg10": "814r", "rg11": "852r"}
pub = pub[pub["bus"] != "xf10"].copy()
pub["dss_bus"] = pub["bus"].replace(name_map)

# 3. Get the OpenDSS voltage for each published bus + phase
def dss_vpu(bus, phase):
    dss.Circuit.SetActiveBus(bus)
    nodes = dss.Bus.Nodes()               # e.g. [1, 2, 3]
    mags = dss.Bus.puVmagAngle()[0::2]    # [mag1, ang1, mag2, ang2, ...] -> magnitudes
    return mags[nodes.index(int(phase))]

pub["dss_v_pu"] = [dss_vpu(b, p) for b, p in zip(pub["dss_bus"], pub["phase"])]
pub["diff_pct"] = (pub["dss_v_pu"] - pub["v_pu"]) / pub["v_pu"] * 100

# 4. Summary
worst = pub.loc[pub["diff_pct"].abs().idxmax()]
print(f"Compared:        {len(pub)} bus-phase voltages")
print(f"Mean |diff|:     {pub['diff_pct'].abs().mean():.2f} %")
print(f"Max  |diff|:     {abs(worst['diff_pct']):.2f} % at bus {worst['bus']} phase {worst['phase']}")
print(f"Within 1%:       {(pub['diff_pct'].abs() <= 1).sum()} of {len(pub)}")

# Regulator taps (IEEE published: RG10 = 12/5/5, RG11 = 13/11/12)
for reg in ["reg1a", "reg1b", "reg1c", "reg2a", "reg2b", "reg2c"]:
    dss.Transformers.Name(reg)
    dss.Transformers.Wdg(2)
    print(f"{reg} tap: {round((dss.Transformers.Tap() - 1) / 0.00625):+d}")

pub.to_csv(here / f"results_step2_{tag}.csv", index=False)

# 5. Voltage profile plot
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.axhspan(0.95, 1.05, color="#e8f2e8", zorder=0, label="ANSI Range A (0.95-1.05 pu)")
ax.scatter(pub["miles_from_sub"], pub["v_pu"], s=60, facecolors="none",
           edgecolors="#555555", linewidths=1.5, label="IEEE published", zorder=2)
ax.scatter(pub["miles_from_sub"], pub["dss_v_pu"], s=20, color="#2a6fdb",
           label="OpenDSS (this study)", zorder=3)
ax.set_xlabel("Distance from substation (miles)")
ax.set_ylabel("Voltage (pu)")
ax.set_title(f"IEEE 34-bus voltage profile, all phases ({tag.replace('_', ' ')})")
ax.grid(color="#dddddd", linewidth=0.6)
ax.legend(loc="lower left", frameon=False)
fig.tight_layout()
fig.savefig(here / f"fig_step2_profile_{tag}.png", dpi=150)
print(f"Saved results_step2_{tag}.csv and fig_step2_profile_{tag}.png")
