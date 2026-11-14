from pathlib import Path
import opendssdirect as dss

# Find the feeder file relative to this script
here = Path(__file__).parent
dss_file = here / "34Bus" / "ieee34Mod1.dss"

# Load the circuit and solve the power flow
dss.Text.Command(f'compile "{dss_file}"')
dss.Solution.Solve()

# Did it solve?
print("Converged: ", dss.Solution.Converged())
print("Iterations:", dss.Solution.Iterations())
print("Circuit:   ", dss.Circuit.Name())
print("Buses:     ", dss.Circuit.NumBuses())

# Power from the substation (OpenDSS shows it negative)
p, q = dss.Circuit.TotalPower()
print(f"Source power: {-p:.1f} kW, {-q:.1f} kvar")
print(f"Losses:       {dss.Circuit.Losses()[0]/1000:.1f} kW")

# Lowest and highest node voltage, in per-unit
names = dss.Circuit.AllNodeNames()
vpu = dss.Circuit.AllBusMagPu()
lo = min(range(len(vpu)), key=vpu.__getitem__)
hi = max(range(len(vpu)), key=vpu.__getitem__)
print(f"Min V: {vpu[lo]:.4f} pu at {names[lo]}")
print(f"Max V: {vpu[hi]:.4f} pu at {names[hi]}")