"""Step 6: One-line diagram of the IEEE 34-bus feeder, drawn from the OpenDSS model itself.

Topology (lines, transformers, regulators, capacitors) is read from OpenDSS, and bus
positions from the EPRI coordinate file, so the drawing always matches the model.
"""
from pathlib import Path
import pandas as pd
import opendssdirect as dss
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

here = Path(__file__).parent
PV_BUS, LIMIT_BUS = "848", "814"

dss.Text.Command(f'compile "{here / "34Bus" / "ieee34Mod1.dss"}"')
xy = pd.read_csv(here / "34Bus" / "IEEE34_BusXY.csv", header=None, names=["bus", "x", "y"])
xy["bus"] = xy["bus"].str.lower()
pos = {r.bus: (r.x, r.y) for r in xy.itertuples()}

INK, MUTED, ACCENT, PV_BLUE = "#222222", "#888888", "#c2410c", "#2a6fdb"
fig, ax = plt.subplots(figsize=(13, 7))

# ---- Lines: thick = 3-phase, thin = 1-phase ----
for name in dss.Lines.AllNames():
    dss.Lines.Name(name)
    b1, b2 = dss.Lines.Bus1().split(".")[0], dss.Lines.Bus2().split(".")[0]
    (x1, y1), (x2, y2) = pos[b1], pos[b2]
    three = dss.Lines.Phases() == 3
    ax.plot([x1, x2], [y1, y2], color=INK if three else MUTED,
            lw=2.4 if three else 1.2, solid_capstyle="round", zorder=1)


def xfmr_symbol(b1, b2, label, color=INK, off=(0, 26), ha="center"):
    """Two overlapping circles between two buses (transformer / regulator)."""
    (x1, y1), (x2, y2) = pos[b1], pos[b2]
    ax.plot([x1, x2], [y1, y2], color=color, lw=2.4, zorder=1)
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = (x2 - x1), (y2 - y1)
    n = max((dx ** 2 + dy ** 2) ** 0.5, 1)
    ux, uy = dx / n, dy / n
    for s in (-1, 1):
        ax.add_patch(Circle((mx + s * 45 * ux, my + s * 45 * uy), 70, fill=True,
                            facecolor="white", edgecolor=color, lw=1.8, zorder=3))
    ax.annotate(label, (mx, my), xytext=off, textcoords="offset points",
                ha=ha, va="center", fontsize=8.5, color=color, zorder=5)


# ---- Transformers and regulators from the model ----
labels = {"subxf": "Substation\n69/24.9 kV, 2.5 MVA", "xfm1": "XFM1\n24.9/4.16 kV, 500 kVA"}
seen_banks = set()
for name in dss.Transformers.AllNames():
    dss.Circuit.SetActiveElement(f"Transformer.{name}")
    b1, b2 = [b.split(".")[0] for b in dss.CktElement.BusNames()[:2]]
    if name.startswith("reg"):
        bank = name[:4]                       # reg1a/b/c -> one 3-phase regulator bank
        if bank in seen_banks:
            continue
        seen_banks.add(bank)
        tag = "RG10" if bank == "reg1" else "RG11"
        if tag == "RG10":
            xfmr_symbol(b1, b2, "RG10 regulator", off=(0, 32))
        else:
            xfmr_symbol(b1, b2, "RG11\nregulator", off=(-22, 0), ha="right")
    elif name == "xfm1":
        xfmr_symbol(b1, b2, "")
        x8, y8 = (pos["888"][0] + pos["890"][0]) / 2, pos["888"][1]
        ax.annotate(labels[name], (x8, y8), xytext=(0, 24), textcoords="offset points",
                    ha="center", va="center", fontsize=8.5, color=INK)
    else:
        xfmr_symbol(b1, b2, labels.get(name, name), off=(0, 40))

# ---- Capacitors ----
for name in dss.Capacitors.AllNames():
    dss.Capacitors.Name(name)
    dss.Circuit.SetActiveElement(f"Capacitor.{name}")
    b = dss.CktElement.BusNames()[0].split(".")[0]
    x, y = pos[b]
    ax.plot([x, x + 160], [y, y], color=INK, lw=1.2, zorder=2)
    ax.plot([x + 160, x + 160], [y - 60, y + 60], color=INK, lw=2, zorder=2)
    ax.plot([x + 190, x + 190], [y - 60, y + 60], color=INK, lw=2, zorder=2)
    ax.text(x + 220, y, f"{name.upper()} {dss.Capacitors.kvar():.0f} kvar",
            va="center", fontsize=8.5, color=INK)

# ---- Source ----
sx, sy = pos["sourcebus"]
ax.add_patch(Circle((sx - 90, sy), 80, facecolor="white", edgecolor=INK, lw=1.8, zorder=3))
ax.text(sx - 90, sy, "~", ha="center", va="center", fontsize=14, zorder=4)
ax.plot([sx - 10, sx], [sy, sy], color=INK, lw=2.4)
ax.text(sx - 90, sy - 170, "69 kV source", ha="center", fontsize=8.5)

# ---- PV at bus 848 ----
px, py = pos[PV_BUS]
ax.plot([px, px - 300], [py, py], color=PV_BLUE, lw=1.8, zorder=2)
ax.add_patch(Rectangle((px - 520, py - 90), 220, 180, facecolor="white",
                       edgecolor=PV_BLUE, lw=2, zorder=3))
ax.text(px - 410, py, "PV", ha="center", va="center", color=PV_BLUE, fontsize=10, weight="bold", zorder=4)
ax.text(px - 560, py, "PV hosting capacity:\n800 kW unity PF\n900 kW volt-var\n1,050 kW 0.95 PF",
        ha="right", va="center", fontsize=8.5, color=PV_BLUE)

# ---- Limiting bus ----
lx, ly = pos[LIMIT_BUS]
ax.add_patch(Circle((lx, ly), 75, fill=False, edgecolor=ACCENT, lw=2, zorder=4))
ax.annotate("Limiting bus 814\n(end of unregulated section)", (lx, ly), xytext=(0, -48),
            textcoords="offset points", ha="center", va="center", fontsize=8.5, color=ACCENT)

# ---- Bus dots and names ----
for b, (x, y) in pos.items():
    if b == "sourcebus":
        continue
    ax.plot(x, y, "o", ms=4, color=INK, zorder=4)
    ax.annotate(b, (x, y), xytext=(4, -11), textcoords="offset points", fontsize=7.5, color="#444444")

# ---- Legend, title ----
ax.plot([], [], color=INK, lw=2.4, label="3-phase line (24.9 kV; 4.16 kV beyond XFM1)")
ax.plot([], [], color=MUTED, lw=1.2, label="1-phase lateral")
ax.legend(loc="lower right", frameon=False, fontsize=9)
ax.set_title("IEEE 34-bus feeder one-line diagram (drawn from the OpenDSS model; loads not shown)", fontsize=11, pad=18)
ax.set_aspect("equal")
ax.axis("off")
fig.tight_layout()
fig.savefig(here / "fig_step6_one_line.png", dpi=200)
fig.savefig(here / "fig_step6_one_line.pdf")
print("Saved fig_step6_one_line.png and fig_step6_one_line.pdf")
