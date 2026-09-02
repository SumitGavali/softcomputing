import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

def build_fuzzy_system():
    # 1. Define Antecedents and Consequent
    soh = ctrl.Antecedent(np.arange(0, 101, 1), 'soh')
    soc = ctrl.Antecedent(np.arange(0, 101, 1), 'soc')
    demand = ctrl.Antecedent(np.arange(0, 301, 1), 'demand')
    margin = ctrl.Antecedent(np.arange(-300, 151, 1), 'margin')
    
    urgency = ctrl.Consequent(np.arange(0, 101, 1), 'urgency')

    # 2. Define Membership Functions
    soh['LOW'] = fuzz.trapmf(soh.universe, [0, 0, 35, 55])
    soh['MEDIUM'] = fuzz.trimf(soh.universe, [40, 65, 80])
    soh['HIGH'] = fuzz.trapmf(soh.universe, [70, 85, 100, 100])

    soc['LOW'] = fuzz.trapmf(soc.universe, [0, 0, 25, 45])
    soc['MEDIUM'] = fuzz.trimf(soc.universe, [35, 55, 75])
    soc['HIGH'] = fuzz.trapmf(soc.universe, [65, 80, 100, 100])

    demand['LOW'] = fuzz.trapmf(demand.universe, [0, 0, 20, 50])
    demand['MEDIUM'] = fuzz.trimf(demand.universe, [30, 65, 120])
    demand['HIGH'] = fuzz.trapmf(demand.universe, [90, 150, 300, 300])

    margin['CRITICAL_DEFICIT'] = fuzz.trapmf(margin.universe, [-300, -300, -40, -15])
    margin['DEFICIT'] = fuzz.trimf(margin.universe, [-30, -10, 5])
    margin['SAFE'] = fuzz.trimf(margin.universe, [0, 25, 60])
    margin['HIGH_MARGIN'] = fuzz.trapmf(margin.universe, [40, 75, 150, 150])

    urgency['LOW'] = fuzz.trapmf(urgency.universe, [0, 0, 20, 40])
    urgency['MEDIUM'] = fuzz.trimf(urgency.universe, [25, 50, 75])
    urgency['HIGH'] = fuzz.trimf(urgency.universe, [60, 80, 95])
    urgency['CRITICAL'] = fuzz.trapmf(urgency.universe, [85, 95, 100, 100])

    rules = []
    
    # LEVEL 1
    rules.append(ctrl.Rule(margin['CRITICAL_DEFICIT'], urgency['CRITICAL']))

    # LEVEL 1.5 - DEFICIT
    rules.append(ctrl.Rule(margin['DEFICIT'] & soh['LOW'], urgency['CRITICAL']))
    rules.append(ctrl.Rule(margin['DEFICIT'] & soc['LOW'], urgency['CRITICAL']))
    rules.append(ctrl.Rule(margin['DEFICIT'] & demand['HIGH'], urgency['CRITICAL']))
    
    # DEFICIT AND (SoH=MED or HIGH) AND (SOC=MED or HIGH) AND (Dem=LOW or MED) -> HIGH
    for soh_val in ['MEDIUM', 'HIGH']:
        for soc_val in ['MEDIUM', 'HIGH']:
            for demand_val in ['LOW', 'MEDIUM']:
                rules.append(ctrl.Rule(margin['DEFICIT'] & soh[soh_val] & soc[soc_val] & demand[demand_val], urgency['HIGH']))

    # LEVEL 3 - HIGH_MARGIN
    rules.append(ctrl.Rule(margin['HIGH_MARGIN'] & soh['LOW'], urgency['MEDIUM']))
    rules.append(ctrl.Rule(margin['HIGH_MARGIN'] & soh['MEDIUM'], urgency['LOW']))
    rules.append(ctrl.Rule(margin['HIGH_MARGIN'] & soh['HIGH'], urgency['LOW']))

    # LEVEL 2 (SAFE)
    # Define HIGH risk states explicitly
    rules.append(ctrl.Rule(margin['SAFE'] & soh['LOW'] & soc['LOW'], urgency['HIGH']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['LOW'] & demand['HIGH'], urgency['HIGH']))
    rules.append(ctrl.Rule(margin['SAFE'] & soc['LOW'] & demand['HIGH'], urgency['HIGH']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['LOW'] & soc['MEDIUM'] & demand['MEDIUM'], urgency['HIGH']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['MEDIUM'] & soc['LOW'] & demand['MEDIUM'], urgency['HIGH']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['MEDIUM'] & soc['MEDIUM'] & demand['HIGH'], urgency['HIGH']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['HIGH'] & soc['LOW'] & demand['HIGH'], urgency['HIGH']))

    # Define LOW risk states explicitly
    rules.append(ctrl.Rule(margin['SAFE'] & soh['HIGH'] & soc['HIGH'] & demand['LOW'], urgency['LOW']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['HIGH'] & soc['HIGH'] & demand['MEDIUM'], urgency['LOW']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['HIGH'] & soc['MEDIUM'] & demand['LOW'], urgency['LOW']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['MEDIUM'] & soc['HIGH'] & demand['LOW'], urgency['LOW']))
    
    # Define MEDIUM risk states explicitly
    rules.append(ctrl.Rule(margin['SAFE'] & soh['LOW'] & soc['MEDIUM'] & demand['LOW'], urgency['MEDIUM']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['LOW'] & soc['HIGH'] & demand['LOW'], urgency['MEDIUM']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['LOW'] & soc['HIGH'] & demand['MEDIUM'], urgency['MEDIUM']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['MEDIUM'] & soc['LOW'] & demand['LOW'], urgency['MEDIUM']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['MEDIUM'] & soc['MEDIUM'] & demand['LOW'], urgency['MEDIUM']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['MEDIUM'] & soc['MEDIUM'] & demand['MEDIUM'], urgency['MEDIUM']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['MEDIUM'] & soc['HIGH'] & demand['MEDIUM'], urgency['MEDIUM']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['MEDIUM'] & soc['HIGH'] & demand['HIGH'], urgency['MEDIUM']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['HIGH'] & soc['LOW'] & demand['LOW'], urgency['MEDIUM']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['HIGH'] & soc['LOW'] & demand['MEDIUM'], urgency['MEDIUM']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['HIGH'] & soc['MEDIUM'] & demand['MEDIUM'], urgency['MEDIUM']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['HIGH'] & soc['MEDIUM'] & demand['HIGH'], urgency['MEDIUM']))
    rules.append(ctrl.Rule(margin['SAFE'] & soh['HIGH'] & soc['HIGH'] & demand['HIGH'], urgency['MEDIUM']))

    # 4. Build Control System
    system = ctrl.ControlSystem(rules)
    simulator = ctrl.ControlSystemSimulation(system)
    
    return simulator, system, soh, soc, demand, margin, urgency

def get_urgency(simulator, soh_val, soc_val, demand_val, margin_val):
    simulator.input['soh'] = np.clip(soh_val, 0, 100)
    simulator.input['soc'] = np.clip(soc_val, 0, 100)
    simulator.input['demand'] = np.clip(demand_val, 0, 300)
    simulator.input['margin'] = np.clip(margin_val, -300, 150)
    simulator.compute()
    return simulator.output['urgency']
