"""Step 4: Bar chart comparing PV hosting capacity at bus 848 for each inverter mode."""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

here = Path(__file__).parent
cases = [  # (label, csv file)
    ("Unity PF\n1.05 pu source (IEEE)", "results_step3_hc_bus848_src1.05_step50_unity.csv"),
    ("Unity PF\n1.03 pu source", "results_step3_hc_bus848_src1.03_step50_unity.csv"),
    ("Volt-var\n(IEEE 1547 Cat B)", "results_step3_hc_bus848_src1.03_step50_vv.csv"),
    ("0.95 PF absorbing", "results_step3_hc_bus848_src1.03_step50_pf95.csv"),
]

rows = []
for label, f in cases:
    d = pd.read_csv(here / f)
    hc = int(d.loc[d["pass_"], "pv_kw"].max())
    fail = d.loc[~d["pass_"] & (d["pv_kw"] > 0)].iloc[0]
    rows.append(dict(case=label.replace("\n", " "), hosting_capacity_kw=hc,
                     first_fail_kw=int(fail["pv_kw"]), fail_vmax_pu=fail["vmax_pu"],
                     fail_node=fail["vmax_node"], fail_hour=int(fail["vmax_hour"])))
    print(f"{label.replace(chr(10), ' '):38s} HC {hc:5d} kW   first fail {int(fail['pv_kw'])} kW "
          f"at {fail['vmax_pu']:.4f} pu ({fail['vmax_node']}, hr {int(fail['vmax_hour'])})")

summary = pd.DataFrame(rows)
summary.to_csv(here / "results_step4_summary.csv", index=False)

fig, ax = plt.subplots(figsize=(8, 4.5))
x = range(len(cases))
bars = ax.bar(x, summary["hosting_capacity_kw"], width=0.55, color="#2a6fdb")
for b, v in zip(bars, summary["hosting_capacity_kw"]):
    ax.text(b.get_x() + b.get_width() / 2, v + 20, f"{v} kW", ha="center", va="bottom", fontsize=10)
ax.set_xticks(list(x), [c[0] for c in cases])
ax.set_ylabel("PV hosting capacity at bus 848 (kW)")
ax.set_title("IEEE 34-bus PV hosting capacity by inverter mode (full-year hourly, ANSI Range A)")
ax.set_ylim(0, summary["hosting_capacity_kw"].max() * 1.15)
ax.grid(axis="y", color="#dddddd", linewidth=0.6)
ax.set_axisbelow(True)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig(here / "fig_step4_hosting_capacity.png", dpi=150)
print("Saved results_step4_summary.csv and fig_step4_hosting_capacity.png")
