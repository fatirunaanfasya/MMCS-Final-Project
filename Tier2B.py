import xpress as xp
import pandas as pd
import numpy as np
from pathlib import Path
from itertools import product
from ExportSolutions import export_to_excel

# ==========================================
# 1. IMPORT DATA
# ==========================================

prob = xp.problem(name="Tier1")

# Directory containing this .py file
script_dir = Path(__file__).resolve().parent
#Extracting forecasted data
electricity_prices_df = pd.read_excel(script_dir/"Data/Forecasts/electricity_prices_low_normal_high.xlsx")
electricity_demand_df = pd.read_excel(script_dir/"Data/Forecasts/demand_scenarios_2026-2027.xlsx")
electricity_generation_df = pd.read_excel(script_dir/"Data/Forecasts/wind_scenarios_2026_2027 forcast.xlsx")
hydrogen_prices_df = pd.read_excel(script_dir/"Data/Forecasts/hydrogen_prices_low_normal_high.xlsx")

# Dictionary containing your dataframes
dataframes = {
    "electricity_price": electricity_prices_df,
    "demand": electricity_demand_df,
    "generation": electricity_generation_df,
    "hydrogen_price": hydrogen_prices_df
}

# Extract scenario names from each dataframe
scenario_columns = {
    name: [col for col in df.columns if col != "date"]
    for name, df in dataframes.items()
}

# Generate all possible combinations
combinations = list(product(*scenario_columns.values()))

print(f"Total scenarios: {len(combinations)}")

# Generate NumPy arrays
market_price = []
demand = []
generation = []
hydrogen_price = []

for combination in combinations:

    arrays = [
        df[column].to_numpy()
        for df, column in zip(dataframes.values(), combination)
    ]

    market_price.append(arrays[0])
    demand.append(arrays[1])
    generation.append(arrays[2])
    hydrogen_price.append(arrays[3])

# Convert to NumPy arrays
market_price = np.array(market_price)
demand = np.array(demand)
generation = np.array(generation)
hydrogen_price = np.array(hydrogen_price)


number_scenarios = market_price.shape[0]
number_days=market_price.shape[1]


scenario_probabilities=[1/number_scenarios]*number_scenarios



# IMPORTANT:
# Assumption: generation and demand are daily energy (MWh).
# If the source is daily average MW, convert to MWh first.
demand=24*demand
generation=24*generation

surplus = np.maximum(generation - demand, 0)
deficit = np.maximum(demand - generation, 0)

# ==========================================
# 2. PARAMETERS
# ==========================================

unit_battery_cost = 35000000
#unit_battery_cost = 24037488     # GBP/unit, assumed
unit_hydrogen_cost = 15000000  # GBP/unit

#purchase_price = [abs(market_price[t])*2 for t in range(number_days)]          # GBP/MWh
hydrogen_yield = 55.9        # kWh/kg

battery_duration = 2         # hours
battery_efficiency = 0.90
# ------------------------------------
# 2.1 CVaR Parameters
# ------------------------------------
lambda_=0.75
alpha=0.90 
# ------------------------------------
# 2.1 Annualization Parameters
# ------------------------------------
discount_rate = 0.05
lifetime = 15
crf = (
    discount_rate * (1 + discount_rate)**lifetime
    / ((1 + discount_rate)**lifetime - 1)
)


max_hydrogen_cap=max(float(surplus.max()), 0)*2

# Capacity bounds are derived from the data
# for numerical stability, not imposed as
# arbitrary investment targets.

max_battery_MW = 2*max(float(surplus.max()), 0)
max_hydrogen_MW = max(float(surplus.max()), 0)

# ==========================================
# 3. INVESTMENT DECISION VARIABLES
# ==========================================

battery_units = prob.addVariable(
    vartype=xp.integer,
    lb=0,
    name="battery_units"
)

electrolizer_units = prob.addVariable(
    vartype=xp.integer,
    lb=0,
    name="electrolyzer_units"
)

battery_installation_MW=50*battery_units

hydrogen_installation_MW=20*electrolizer_units

# ==========================================
# 4. DAILY OPERATION VARIABLES
# ==========================================

def scenario_daily_variables(name):
    return [
        [
            prob.addVariable(name=f"{name}_{s+1}_{t+1}", lb=0)
            for t in range(number_days)
        ]
        for s in range(number_scenarios)
    ]

battery_charge = scenario_daily_variables("battery_charge")
battery_discharge = scenario_daily_variables("battery_discharge")
battery_stored = scenario_daily_variables("battery_stored")


hydrogen_electricity = scenario_daily_variables("hydrogen_electricity")
electricity_purchase = scenario_daily_variables("electricity_purchase")
electricity_sold = scenario_daily_variables("electricity_sold")
curtailment = scenario_daily_variables("curtailment")

is_charging = [[prob.addVariable(vartype=xp.binary, name=f"is_charging_{s+1}_{t+1}") for t in range(number_days)]for s in range(number_scenarios)]
is_discharging = [[prob.addVariable(vartype=xp.binary, name=f"is_discharging_{s+1}_{t+1}") for t in range(number_days)]for s in range(number_scenarios)]
# =========================================
# 4.1 CVaR AUXILIARY VARIABLES
# =========================================

eta = prob.addVariable(
    name="eta",
    lb=-xp.infinity
)

z = [prob.addVariable(name=f"z_{s}",lb=0) for s in range(number_scenarios)]

# ==========================================
# 5. ELECTRICITY DEMAND
# ==========================================
electricity_demand_lb=[[
    electricity_sold[s][t]>= (generation[s][t]*0.8 if 0.8*generation[s][t]<=demand[s][t] else demand[s][t])
    for t in range(number_days)
]for s in range(number_scenarios)]

electricity_demand_ub=[[
    electricity_sold[s][t]<=demand[s][t]
    for t in range(number_days)
]for s in range(number_scenarios)]

# ==========================================
# 6. BALANCE EQUATIONS
# ==========================================

# Battery discharge reduces grid purchases.

global_balance = [[
    generation[s][t] + battery_discharge[s][t]==
    hydrogen_electricity[s][t]+battery_charge[s][t]+electricity_sold[s][t]+curtailment[s][t]
    for t in range(number_days)
]for s in range(number_scenarios)]
demand_balance=[[
    electricity_sold[s][t]+electricity_purchase[s][t]==demand[s][t]
    for t in range(number_days)
]for s in range(number_scenarios)]

# ==========================================
# 7. BATTERY STORAGE
# ==========================================

# Battery installation in MW
# Battery energy capacity = 2 * MW

battery_energy_capacity = (
    battery_duration * battery_installation_MW
)

# Initial SoC = 20%
initial_soc = 0.2 * battery_energy_capacity

battery_balance = [[
    battery_stored[s][t] ==
    (
        initial_soc if t == 0
        else battery_stored[s][t-1]
    )
    + battery_efficiency * battery_charge[s][t]
    - battery_discharge[s][t]
    for t in range(number_days)
]for s in range(number_scenarios)]

battery_minimum = [[
    battery_stored[s][t] >=
    0.2 * battery_energy_capacity
    for t in range(number_days)
]for s in range(number_scenarios)]

battery_maximum = [[
    battery_stored[s][t] <=
    0.8 * battery_energy_capacity
    for t in range(number_days)
]for s in range(number_scenarios)]

battery_discharge_min=[[
    battery_discharge[s][t]<=battery_stored[s][t]
    for t in range(number_days)
]for s in range(number_scenarios)]

mutual_exclusion=[[
    is_charging[s][t] + is_discharging[s][t] <= 1
    for t in range(number_days)
]for s in range(number_scenarios)]

battery_charge_limit = [[
    battery_charge[s][t] <= max_battery_MW * is_charging[s][t]*24*0.6
    for t in range(number_days)
]for s in range(number_scenarios)]

battery_discharge_limit = [[
    battery_discharge[s][t] <= max_battery_MW * is_discharging[s][t]*24*0.6
    for t in range(number_days)
]for s in range(number_scenarios)]

# Prevent terminal energy being left as
# an unaccounted investment benefit

#terminal_soc = [
#    battery_stored[-1] == initial_soc
#]

# ==========================================
# 8. HYDROGEN PRODUCTION
# ==========================================

# LP relaxation: 0%-100% operation.
# Exact 20% minimum when ON needs binary
# variables, which would make this MILP.

#Look into hydrogen storage
hydrogen_capacity_limit = [[
    hydrogen_electricity[s][t]/24 <=
    hydrogen_installation_MW
    for t in range(number_days)
]for s in range(number_scenarios)]

#hydrogen_capacity_limit_big_M=[
#    hydrogen_electricity[t]/24 <=
#        max_hydrogen_cap*produce_hydrogen[t]
#        for t in range(number_days)
#]

hydrogen_capacity_lb=[[
    hydrogen_electricity[s][t]/24>=0.2*hydrogen_installation_MW#-(1-produce_hydrogen[t])*max_hydrogen_cap*0.2
    for t in range(number_days)
]for s in range(number_scenarios)]

# ==========================================
# 9. OBJECTIVE FUNCTION
# ==========================================

# One-time investment costs

battery_capex = (
    battery_units * unit_battery_cost
)

hydrogen_capex = (
    electrolizer_units * unit_hydrogen_cost
)

total_capex = battery_capex + hydrogen_capex

annualised_capex=total_capex*crf
# Hydrogen revenue
hydrogen_revenue = [
    xp.Sum(
        hydrogen_electricity[s][t]
        * 1000 / hydrogen_yield
        * hydrogen_price[s][t]
        for t in range(number_days)
    )
    for s in range(number_scenarios)
]

# Electricity profits
electricity_revenue = [
    xp.Sum(
        electricity_sold[s][t] * market_price[s][t]
        for t in range(number_days)
    )
    for s in range(number_scenarios)
]

# Expected net investment benefit
net_investment_benefit = {
    s: (hydrogen_revenue[s] + electricity_revenue[s]-annualised_capex)
    for s in range(number_scenarios)
}


# ==========================================
# 10. CVaR CONSTRAINTS
# ==========================================
shortfall_constraint=[
    z[s]>=eta-net_investment_benefit[s]
    for s in range(number_scenarios)
]

expected_profit=xp.Sum(
    scenario_probabilities[s]*net_investment_benefit[s]
    for s in range(number_scenarios)
)
# -----------------------------
# CVaR
# -----------------------------


# ==========================================
# 11. ADD CONSTRAINTS
# ==========================================

prob.addConstraint(
    electricity_demand_lb,
    electricity_demand_ub,
    global_balance,
    demand_balance,
    battery_balance,
    battery_minimum,
    battery_maximum,
    battery_discharge_min,
    mutual_exclusion,
    battery_charge_limit,
    battery_discharge_limit,
    hydrogen_capacity_limit,
    hydrogen_capacity_lb,
    shortfall_constraint
)
# ==========================================
# 12. SOLVE
# ==========================================

results=[]
alphas = np.round(np.append(np.arange(0.80, 0.96, 0.05), 0.99), 2)
for alpha in alphas:
    for lambda_ in np.arange(0,1.01,0.1):
        cvar = eta - (1 / (1 - alpha)) * xp.Sum(
            scenario_probabilities[s] * z[s]
            for s in range(number_scenarios)
    )
        objective = (
            (1 - lambda_) * expected_profit
            + lambda_ * cvar
        )

        prob.setObjective(
            objective,
            sense=xp.maximize
        )
        print("======================")
        print("ITERATION DONE")
        print("======================")
        print(alpha)
        print(lambda_)
        prob.solve()

        results.append({
            "alpha":alpha,
            "lambda": lambda_,
            "objective": prob.getObjVal(),
            "expected_profit": prob.getSolution(expected_profit),
            "cvar": prob.getSolution(cvar),
            "eta":prob.getSolution(eta),
            "Battery":prob.getSolution(battery_units),
            "Hydrogen":prob.getSolution(electrolizer_units)
        })

    iterations=pd.DataFrame(results)
    iterations.to_excel("test.xlsx")


prob.writeProb ("tier2B","lp")

print("Solve done")
# ==========================================
# TIER 2 - COMPLETE EXCEL RESULTS EXPORT
# ==========================================

import pandas as pd
import numpy as np
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
def summary_Excel():
    if prob.attributes.solstatus != 1:
        print("No optimal solution. Excel not exported.")


def create_Excel():
    if prob.attributes.solstatus != 1:
        print("No optimal solution. Excel not exported.")

    else:
        # --------------------------------------
        # 1. INVESTMENT DECISIONS
        # --------------------------------------

        battery_MW = prob.getSolution(battery_installation)
        battery_MWh = battery_MW * battery_duration
        hydrogen_MW = prob.getSolution(hydrogen_installation)

        battery_capex_value = battery_MWh * battery_cost
        hydrogen_capex_value = hydrogen_MW * hydrogen_cost
        total_capex_value = battery_capex_value + hydrogen_capex_value

        # --------------------------------------
        # 2. DAILY DECISION VARIABLE RESULTS
        # --------------------------------------

        dates = (
            pd.to_datetime(raw_data_df["date"])
            if "date" in raw_data_df.columns
            else pd.Series(pd.date_range(
                "2020-01-01", periods=number_days
            ))
        )

        records=[
            {
                "Scenario":s,
                "Date":t,
                "Generation_MWh":generation[s][t],
                "Demand_Mwh":demand[s][t],
                "Market_Price_GBP_MWh": market_price[s][t],
                "Initial_Surplus_MWh": surplus[s][t],
                "Initial_Deficit_MWh": deficit[s][t],
                "Electricity_sold":prob.getSolution(electricity_sold[s][t]),
                "Battery_Charge_MWh":prob.getSolution(battery_charge[s][t]),
                "Battery_Discharge_MWh":prob.getSolution(battery_discharge[s][t]),
                "Battery_Stored_MWh":prob.getSolution(battery_stored[s][t]),
                "Hydrogen_Electricity_MWh":prob.getSolution(hydrogen_electricity[s][t]),
                "Electricity_Purchased_MWh":prob.getSolution(electricity_purchase[s][t]),
                "Electricity_Curtailed_MWh":prob.getSolution(curtailment[s][t])
            }
            for t in range(number_days)
            for s in range(number_scenarios)
        ]
        daily = pd.DataFrame(records)

        # --------------------------------------
        # 3. HYDROGEN PRODUCTION AND SALES
        # --------------------------------------

        daily["Hydrogen_Produced_kg"] = (
            daily["Hydrogen_Electricity_MWh"]
            * 1000 / hydrogen_yield
        )

        # Assumption: all hydrogen produced is sold.
        # No hydrogen storage or unsold inventory.

        daily["Hydrogen_Revenue_GBP"] = (
            daily["Hydrogen_Produced_kg"]
            * hydrogen_price
        )

        daily["Electricity_Revenue_GBP"]=(
            daily["Electricity_sold"]*daily["Market_Price_GBP_MWh"]
        )

        # --------------------------------------
        # 4. BATTERY AND ELECTRICITY FINANCIALS
        # --------------------------------------


        daily["Incremental_Cashflow_GBP"] = (
            daily["Hydrogen_Revenue_GBP"]
            + daily["Electricity_Revenue_GBP"]
        )

        # --------------------------------------
        # 5. TOTAL OPERATIONS
        # --------------------------------------

        total_surplus = daily["Initial_Surplus_MWh"].sum()
        total_deficit = daily["Initial_Deficit_MWh"].sum()

        total_battery_charge = daily["Battery_Charge_MWh"].sum()
        total_battery_discharge = daily["Battery_Discharge_MWh"].sum()

        max_battery_stored = daily["Battery_Stored_MWh"].max()

        total_hydrogen_electricity = daily[
            "Hydrogen_Electricity_MWh"
        ].sum()

        total_hydrogen_produced = daily[
            "Hydrogen_Produced_kg"
        ].sum()

        total_hydrogen_sold = daily[
            "Hydrogen_Produced_kg"
        ].sum()

        total_electricity_purchased = daily[
            "Electricity_Purchased_MWh"
        ].sum()

        total_curtailed = daily[
            "Electricity_Curtailed_MWh"
        ].sum()

        total_hydrogen_revenue = daily[
            "Hydrogen_Revenue_GBP"
        ].sum()

        total_incremental_cashflow = daily[
            "Incremental_Cashflow_GBP"
        ].sum()

        net_profit = total_incremental_cashflow - total_capex_value

        captured_surplus = (
            total_battery_charge + total_hydrogen_electricity
        )

        capture_rate = (
            captured_surplus / total_surplus * 100
            if total_surplus > 0 else 0
        )

        # --------------------------------------
        # 6. INVESTMENT SUMMARY
        # --------------------------------------

        summary_items = [
            ("Battery Installed Capacity", battery_MW, "MW"),
            ("Battery Energy Capacity", battery_MWh, "MWh"),
            ("Hydrogen Installed Capacity", hydrogen_MW, "MW"),

            ("Total Initial Surplus", total_surplus, "MWh"),
            ("Total Initial Deficit", total_deficit, "MWh"),

            ("Total Battery Charging", total_battery_charge, "MWh"),
            ("Total Battery Discharging", total_battery_discharge, "MWh"),
            ("Maximum Battery Stored", max_battery_stored, "MWh"),

            ("Electricity Used for Hydrogen",
            total_hydrogen_electricity, "MWh"),

            ("Total Hydrogen Produced", total_hydrogen_produced, "kg"),
            ("Total Hydrogen Sold", total_hydrogen_sold, "kg"),

            ("Total Electricity Purchased",
            total_electricity_purchased, "MWh"),

            ("Total Electricity Curtailed", total_curtailed, "MWh"),
            ("Surplus Captured", captured_surplus, "MWh"),
            ("Surplus Capture Rate", capture_rate, "%"),

            ("Battery CAPEX", battery_capex_value, "GBP"),
            ("Hydrogen CAPEX", hydrogen_capex_value, "GBP"),
            ("Total CAPEX", total_capex_value, "GBP"),

            ("Hydrogen Sales Revenue", total_hydrogen_revenue, "GBP"),
            ("Total Incremental Cash Flow",
            total_incremental_cashflow, "GBP"),

            ("Net Investment Profit", net_profit, "GBP"),
            ("Xpress Objective Value", prob.attributes.objval, "GBP")
        ]

        investment_summary = pd.DataFrame(
            summary_items, columns=["Metric", "Value", "Unit"]
        )

        # --------------------------------------
        # 7. EXPORT AND FORMAT EXCEL
        # --------------------------------------

        output_file = "Tier2_Results.xlsx"

        with pd.ExcelWriter(
            output_file, engine="openpyxl"
        ) as writer:

            sheets = {
                "Investment Summary": investment_summary,
                "Daily Operations": daily,
            }

            for sheet_name, dataframe in sheets.items():
                dataframe.to_excel(
                    writer, sheet_name=sheet_name, index=False
                )

                ws = writer.sheets[sheet_name]
                ws.freeze_panes = "A2"
                ws.auto_filter.ref = ws.dimensions

                for cell in ws[1]:
                    cell.font = Font(
                        bold=True, color="FFFFFF"
                    )
                    cell.fill = PatternFill(
                        "solid", fgColor="17365D"
                    )
                    cell.alignment = Alignment(
                        horizontal="center"
                    )

                for col in ws.columns:
                    col_letter = get_column_letter(
                        col[0].column
                    )
                    max_length = max(
                        len(str(cell.value))
                        if cell.value is not None else 0
                        for cell in col
                    )
                    ws.column_dimensions[col_letter].width = min(
                        max(max_length + 2, 15), 40
                    )

                for row in ws.iter_rows(min_row=2):
                    for cell in row:
                        if isinstance(cell.value, (int, float)):
                            cell.number_format = '#,##0.00;[Red](#,##0.00)'

        # --------------------------------------
        # 11. PRINT KEY RESULTS
        # --------------------------------------


        print(f"\nExcel exported: {output_file}")


        print("\nExcel exported successfully!")
        print("File:", output_file)


    print("Solve Status:", prob.attributes.solvestatus)
    print("Solution Status:", prob.attributes.solstatus)

    if prob.attributes.solstatus == 1:

        battery_MW = prob.getSolution(
            battery_installation
        )

        hydrogen_MW = prob.getSolution(
            hydrogen_installation
        )

        print("\n===== INVESTMENT RESULTS =====")

        print(f"Battery Capacity: {battery_MW:,.2f} MW")
        print(f"Battery Storage: {2*battery_MW:,.2f} MWh")
        print(f"Hydrogen Capacity: {hydrogen_MW:,.2f} MW")

        print(f"Total CAPEX: £{prob.getSolution(total_capex):,.2f}")

        print(
            "Net Investment Benefit: "
            f"£{prob.attributes.objval:,.2f}"
        )

    else:
        print("No optimal solution available.")

