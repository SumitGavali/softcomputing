import numpy as np
import matplotlib.pyplot as plt
from module2.fuzzy_system import build_fuzzy_system, get_urgency
import time

def sanity_test():
    print("--- Sanity Tests ---")
    simulator, _, _, _, _, _, _ = build_fuzzy_system()
    
    val = get_urgency(simulator, 95, 90, 15, 100)
    print(f"A: SoH=95, SOC=90, Demand=15, Margin=100 -> Urgency: {val:.2f} (Expected: LOW-ish)")

    val = get_urgency(simulator, 90, 30, 120, -20)
    print(f"B: SoH=90, SOC=30, Demand=120, Margin=-20 -> Urgency: {val:.2f} (Expected: HIGH/CRITICAL)")

    val = get_urgency(simulator, 20, 90, 10, 100)
    print(f"C: SoH=20, SOC=90, Demand=10, Margin=100 -> Urgency: {val:.2f} (Expected: LOW/MEDIUM, NOT CRITICAL)")

    val = get_urgency(simulator, 20, 30, 120, -100)
    print(f"D: SoH=20, SOC=30, Demand=120, Margin=-100 -> Urgency: {val:.2f} (Expected: CRITICAL)")

    val = get_urgency(simulator, 75, 55, 60, 10)
    print(f"E: SoH=75, SOC=55, Demand=60, Margin=10 -> Urgency: {val:.2f} (Expected: MEDIUM-ish)")
    print()

def generate_plots():
    print("--- Generating Plots ---")
    simulator, system, soh, soc, demand, margin, urgency = build_fuzzy_system()
    
    fig, axes = plt.subplots(5, 1, figsize=(8, 15))
    soh.view(sim=simulator, ax=axes[0])
    axes[0].set_title('SoH')
    soc.view(sim=simulator, ax=axes[1])
    axes[1].set_title('SOC')
    demand.view(sim=simulator, ax=axes[2])
    axes[2].set_title('Demand')
    margin.view(sim=simulator, ax=axes[3])
    axes[3].set_title('Range Margin')
    urgency.view(sim=simulator, ax=axes[4])
    axes[4].set_title('Urgency')
    plt.tight_layout()
    plt.savefig('membership_functions.png')
    plt.close()

    x_margin = np.arange(-100, 151, 15)
    y_soc = np.arange(0, 101, 10)
    X, Y = np.meshgrid(x_margin, y_soc)
    Z = np.zeros_like(X)

    for i in range(X.shape[0]):
        for j in range(X.shape[1]):
            try:
                Z[i, j] = get_urgency(simulator, 80, Y[i, j], 60, X[i, j])
            except Exception:
                Z[i, j] = np.nan

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection='3d')
    ax.plot_surface(X, Y, Z, cmap='viridis')
    ax.set_xlabel('Range Margin')
    ax.set_ylabel('SOC')
    ax.set_zlabel('Urgency')
    ax.set_title('Control Surface (SoH=80, Demand=60)')
    plt.savefig('control_surface.png')
    plt.close()
    print("Plots saved: membership_functions.png, control_surface.png")
    print()

def grid_sweep():
    print("--- Running Grid Sweep Validation ---")
    simulator, _, _, _, _, _, _ = build_fuzzy_system()
    
    soh_range = np.linspace(0, 100, 4)
    soc_range = np.linspace(20, 92, 4)
    demand_range = np.linspace(5, 300, 4)
    margin_range = np.linspace(-300, 150, 4)
    
    total_combinations = len(soh_range) * len(soc_range) * len(demand_range) * len(margin_range)
    print(f"Testing {total_combinations} combinations...")
    
    results = np.zeros((len(soh_range), len(soc_range), len(demand_range), len(margin_range)))
    
    undefined_outputs = 0
    nan_outputs = 0
    
    start_time = time.time()
    for i, soh_val in enumerate(soh_range):
        for j, soc_val in enumerate(soc_range):
            for k, demand_val in enumerate(demand_range):
                for l, margin_val in enumerate(margin_range):
                    try:
                        u = get_urgency(simulator, soh_val, soc_val, demand_val, margin_val)
                        if np.isnan(u):
                            nan_outputs += 1
                            results[i, j, k, l] = np.nan
                        else:
                            results[i, j, k, l] = u
                    except Exception:
                        results[i, j, k, l] = np.nan
                        undefined_outputs += 1
                        
    valid_results = results[~np.isnan(results)]
    min_urg = np.nanmin(valid_results) if len(valid_results) > 0 else 0
    max_urg = np.nanmax(valid_results) if len(valid_results) > 0 else 0
    
    monotonicity_violations = 0
    
    tol = 1e-3
    diff_soh = np.diff(results, axis=0) 
    monotonicity_violations += np.nansum(diff_soh > tol)

    diff_soc = np.diff(results, axis=1) 
    monotonicity_violations += np.nansum(diff_soc > tol)
    
    diff_dem = np.diff(results, axis=2) 
    monotonicity_violations += np.nansum(diff_dem < -tol)
    
    diff_mar = np.diff(results, axis=3) 
    monotonicity_violations += np.nansum(diff_mar > tol)

    print(f"Total Combinations Tested: {total_combinations}")
    print(f"Undefined Outputs: {undefined_outputs}")
    print(f"NaN Outputs: {nan_outputs}")
    print(f"Min Urgency: {min_urg:.2f}")
    print(f"Max Urgency: {max_urg:.2f}")
    print(f"Monotonicity Violations: {monotonicity_violations}")
    print(f"Time taken: {time.time() - start_time:.2f}s")

if __name__ == '__main__':
    sanity_test()
    generate_plots()
    grid_sweep()
