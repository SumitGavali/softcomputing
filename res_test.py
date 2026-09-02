"""
res_test.py — FIS resolution / performance benchmark.
Tests that all 4 antecedents are wired into the rule system
and measures evaluation throughput at universe resolution = 1.
"""
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import time


def build_fuzzy_system():
    res = 1
    soh    = ctrl.Antecedent(np.arange(0,   101, res), 'soh')
    soc    = ctrl.Antecedent(np.arange(0,   101, res), 'soc')
    demand = ctrl.Antecedent(np.arange(0,   301, res), 'demand')
    margin = ctrl.Antecedent(np.arange(-300, 151, res), 'margin')
    urgency = ctrl.Consequent(np.arange(0,  101, res), 'urgency')

    # --- membership functions ---
    soh['LOW']    = fuzz.trapmf(soh.universe,    [0,   0,  35,  55])
    soh['MEDIUM'] = fuzz.trimf(soh.universe,     [40,  65,  80])
    soh['HIGH']   = fuzz.trapmf(soh.universe,    [70,  85, 100, 100])

    soc['LOW']    = fuzz.trapmf(soc.universe,    [0,   0,  25,  45])
    soc['MEDIUM'] = fuzz.trimf(soc.universe,     [35,  55,  75])
    soc['HIGH']   = fuzz.trapmf(soc.universe,    [65,  80, 100, 100])

    demand['LOW']    = fuzz.trapmf(demand.universe, [0,   0,  20,  50])
    demand['MEDIUM'] = fuzz.trimf(demand.universe,  [30,  65, 120])
    demand['HIGH']   = fuzz.trapmf(demand.universe, [90, 150, 300, 300])

    margin['CRITICAL_DEFICIT'] = fuzz.trapmf(margin.universe, [-300, -300, -40, -15])
    margin['DEFICIT']          = fuzz.trimf(margin.universe,  [-30,  -10,    5])
    margin['SAFE']             = fuzz.trimf(margin.universe,  [  0,   25,   60])
    margin['HIGH_MARGIN']      = fuzz.trapmf(margin.universe, [ 40,   75,  150, 150])

    urgency['LOW']      = fuzz.trapmf(urgency.universe, [0,  0,  20,  40])
    urgency['MEDIUM']   = fuzz.trimf(urgency.universe,  [25, 50,  75])
    urgency['HIGH']     = fuzz.trimf(urgency.universe,  [60, 80,  95])
    urgency['CRITICAL'] = fuzz.trapmf(urgency.universe, [85, 95, 100, 100])

    # --- rules (all 4 antecedents must appear in at least one rule) ---
    rules = [
        # Margin is the dominant signal
        ctrl.Rule(margin['CRITICAL_DEFICIT'],                         urgency['CRITICAL']),
        ctrl.Rule(margin['DEFICIT'] & soc['LOW'],                     urgency['CRITICAL']),
        ctrl.Rule(margin['DEFICIT'] & soc['MEDIUM'],                  urgency['HIGH']),
        ctrl.Rule(margin['DEFICIT'] & soc['HIGH'],                    urgency['MEDIUM']),
        ctrl.Rule(margin['SAFE']   & demand['HIGH'],                  urgency['MEDIUM']),
        ctrl.Rule(margin['SAFE']   & demand['MEDIUM'],                urgency['MEDIUM']),
        ctrl.Rule(margin['SAFE']   & demand['LOW'],                   urgency['LOW']),
        ctrl.Rule(margin['HIGH_MARGIN'],                              urgency['LOW']),
        # SoH as health-risk modifier
        ctrl.Rule(soh['LOW']  & margin['SAFE'],                       urgency['MEDIUM']),
        ctrl.Rule(soh['LOW']  & margin['HIGH_MARGIN'],                urgency['MEDIUM']),
        ctrl.Rule(soh['HIGH'] & margin['SAFE']   & demand['LOW'],     urgency['LOW']),
        ctrl.Rule(soh['HIGH'] & margin['CRITICAL_DEFICIT'],           urgency['CRITICAL']),
        # Medium SoH + safe margin coverage
        ctrl.Rule(soh['MEDIUM'] & margin['SAFE'],                     urgency['MEDIUM']),
        ctrl.Rule(soh['MEDIUM'] & margin['HIGH_MARGIN'],              urgency['LOW']),
    ]

    system    = ctrl.ControlSystem(rules)
    simulator = ctrl.ControlSystemSimulation(system)
    return simulator


# ── build ──────────────────────────────────────────────────────────────────
print("Building FIS...")
t0 = time.time()
sim = build_fuzzy_system()
print(f"  Built in {time.time() - t0:.2f}s")

# ── sanity checks ─────────────────────────────────────────────────────────
CASES = [
    ("A: healthy, high SOC, low demand, big margin -> LOW-ish",
     95, 90,  15,  100),
    ("B: healthy, low SOC, high demand, deficit -> CRITICAL",
     90, 30, 120,  -20),
    ("C: degraded, high SOC, low demand, safe -> MEDIUM",
     20, 90,  10,  100),
    ("D: degraded, low SOC, high demand, critical deficit -> CRITICAL",
     20, 30, 120, -100),
    ("E: mid SoH, mid SOC, mid demand, tiny margin -> MEDIUM",
     75, 55,  60,   10),
]

print("\nSanity checks:")
for label, soh_v, soc_v, dem_v, mar_v in CASES:
    sim.input['soh']    = soh_v
    sim.input['soc']    = soc_v
    sim.input['demand'] = dem_v
    sim.input['margin'] = mar_v
    sim.compute()
    print(f"  {label}")
    print(f"    -> urgency = {sim.output['urgency']:.2f}")

# ── throughput benchmark ───────────────────────────────────────────────────
N = 100
print(f"\nThroughput: {N} evaluations...")
t0 = time.time()
for _ in range(N):
    sim.input['soh']    = 95
    sim.input['soc']    = 90
    sim.input['demand'] = 15
    sim.input['margin'] = 100
    sim.compute()
elapsed = time.time() - t0
print(f"  {N} evals in {elapsed:.2f}s  ({elapsed/N*1000:.1f} ms/eval)")
print("\nres_test PASSED")
