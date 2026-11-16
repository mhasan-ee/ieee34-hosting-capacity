"""Substation setpoint trade-off (no PV): overvoltage at light load vs undervoltage at peak load.

Compares IEEE's 1.05 pu source with the 1.03 pu used in this study, over all 8,760 hours.
Bus 814 sits before regulator RG10, so only the substation setpoint controls its voltage.

Usage:
    python setpoint_check.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
import opendssdirect as dss

here = Path(__file__).parent
load_shape = np.array(open(here / "profiles" / "PaperLoadShape.txt").read().replace(",", " ").split(), float)
LIGHT_HR = int(load_shape.argmin())   # lightest load of the year (11 PM, Oct 16; no PV)
PEAK_HR = int(load_shape.argmax())    # peak load of the year (Aug 10, 2 PM)


def solve(hour):
    dss.Solution.LoadMult(load_shape[hour])
    dss.Solution.Solve()
    names = dss.Circuit.AllNodeNames()
    v = np.array(dss.Circuit.AllBusMagPu())
    keep = np.array([not n.startswith("sourcebus") for n in names])
    return np.array(names)[keep], v[keep]


rows = []
for src in [1.05, 1.03]:
    dss.Text.Command(f'compile "{here / "34Bus" / "ieee34Mod1.dss"}"')
    dss.Text.Command(f"vsource.source.pu={src}")

    # Peak first, right after compile (regulator taps depend on the previous solution; see Step 2)
    names, v = solve(PEAK_HR)
    peak_vmin, peak_node = v.min(), names[v.argmin()]
    v814a = v[list(names).index("814.1")]
    n_low = int((v < 0.95).sum())
    names, v = solve(LIGHT_HR)        # bus 814 is unregulated, so its light-load voltage does not depend on taps
    light_vmax, light_node = v.max(), names[v.argmax()]

    hours_814_low = 0                 # hours per year with any phase of bus 814 below 0.95 pu
    for h in range(8760):
        names_h, v_h = solve(h)
        if v_h[[n.startswith("814.") for n in names_h]].min() < 0.95:
            hours_814_low += 1

    rows.append(dict(source_pu=src, light_hr=LIGHT_HR, light_vmax_pu=round(light_vmax, 4), light_node=light_node,
                     peak_hr=PEAK_HR, peak_vmin_pu=round(peak_vmin, 4), peak_node=peak_node,
                     v814a_peak_pu=round(v814a, 4), nodes_below_095_at_peak=n_low,
                     hours_814_below_095=hours_814_low))
    print(f"Source {src} pu: light load max {light_vmax:.4f} pu at {light_node}; peak min {peak_vmin:.4f} pu "
          f"at {peak_node}; 814 A at peak {v814a:.4f} pu; {n_low} nodes < 0.95 at peak; "
          f"814 below 0.95 pu in {hours_814_low} h/yr")

pd.DataFrame(rows).to_csv(here / "results_setpoint_check.csv", index=False)
print("Saved results_setpoint_check.csv")
