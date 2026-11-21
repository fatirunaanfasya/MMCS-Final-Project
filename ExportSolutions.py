# ==========================================
# TIER 1 - COMPLETE EXCEL RESULTS EXPORT
# ==========================================
def export_to_excel(prob):
    import pandas as pd
    import numpy as np
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

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

        daily = pd.DataFrame({
            "Date": dates,
            "Generation_MWh": generation,
            "Demand_MWh": demand,
            "Market_Price_GBP_MWh": market_price,
            "Initial_Surplus_MWh": surplus,
            "Initial_Deficit_MWh": deficit,

            "Electricity_sold":[
                prob.getSolution(electricity_sold[t])
                for t in range(number_days)
            ],
            "Battery_Charge_MWh": [
                prob.getSolution(battery_charge[t])
                for t in range(number_days)
            ],

            "Battery_Discharge_MWh": [
                prob.getSolution(battery_discharge[t])
                for t in range(number_days)
            ],

            "Battery_Stored_MWh": [
                prob.getSolution(battery_stored[t])
                for t in range(number_days)
            ],

            "Hydrogen_Electricity_MWh": [
                prob.getSolution(hydrogen_electricity[t])
                for t in range(number_days)
            ],

            "Electricity_Purchased_MWh": [
                prob.getSolution(electricity_purchase[t])
                for t in range(number_days)
            ],

            "Electricity_Curtailed_MWh": [
                prob.getSolution(curtailment[t])
                for t in range(number_days)
            ]
        })

        # --------------------------------------
        # 3. HYDROGEN PRODUCTION AND SALES
        # --------------------------------------

        daily["Hydrogen_Produced_kg"] = (
            daily["Hydrogen_Electricity_MWh"]
            * 1000 / hydrogen_yield
        )

        # Assumption: all hydrogen produced is sold.
        # No hydrogen storage or unsold inventory.

        daily["Hydrogen_Sold_kg"] = (
            daily["Hydrogen_Produced_kg"]
        )

        daily["Hydrogen_Revenue_GBP"] = (
            daily["Hydrogen_Sold_kg"]
            * hydrogen_price
        )

        # --------------------------------------
        # 4. BATTERY AND ELECTRICITY FINANCIALS
        # --------------------------------------

        daily["Electricity_Purchase_Cost_GBP"] = (
            daily["Electricity_Purchased_MWh"]
            * purchase_price
        )

        daily["Baseline_Purchase_Cost_GBP"] = (
            daily["Initial_Deficit_MWh"]
            * purchase_price
        )

        daily["Battery_Savings_GBP"] = (
            daily["Baseline_Purchase_Cost_GBP"]
            - daily["Electricity_Purchase_Cost_GBP"]
        )

        daily["Incremental_Cashflow_GBP"] = (
            daily["Hydrogen_Revenue_GBP"]
            + daily["Battery_Savings_GBP"]
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
            "Hydrogen_Sold_kg"
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

        total_battery_savings = daily[
            "Battery_Savings_GBP"
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
            ("Battery Cost Savings", total_battery_savings, "GBP"),
            ("Total Incremental Cash Flow",
            total_incremental_cashflow, "GBP"),

            ("Net Investment Profit", net_profit, "GBP"),
            ("Xpress Objective Value", prob.attributes.objval, "GBP")
        ]

        investment_summary = pd.DataFrame(
            summary_items, columns=["Metric", "Value", "Unit"]
        )

        # --------------------------------------
        # 7. ANNUAL OPERATIONS
        # --------------------------------------

        daily["Year"] = daily["Date"].dt.year

        annual_operations = daily.groupby(
            "Year", as_index=False
        ).agg(
            Initial_Surplus_MWh=("Initial_Surplus_MWh", "sum"),
            Initial_Deficit_MWh=("Initial_Deficit_MWh", "sum"),
            Battery_Charge_MWh=("Battery_Charge_MWh", "sum"),
            Battery_Discharge_MWh=("Battery_Discharge_MWh", "sum"),
            Maximum_Battery_Stored_MWh=("Battery_Stored_MWh", "max"),
            Hydrogen_Electricity_MWh=("Hydrogen_Electricity_MWh", "sum"),
            Hydrogen_Produced_kg=("Hydrogen_Produced_kg", "sum"),
            Hydrogen_Sold_kg=("Hydrogen_Sold_kg", "sum"),
            Electricity_Purchased_MWh=("Electricity_Purchased_MWh", "sum"),
            Electricity_Curtailed_MWh=("Electricity_Curtailed_MWh", "sum")
        )

        # --------------------------------------
        # 8. ANNUAL FINANCIALS
        # --------------------------------------

        annual_financials = daily.groupby(
            "Year", as_index=False
        ).agg(
            Hydrogen_Revenue_GBP=("Hydrogen_Revenue_GBP", "sum"),
            Battery_Savings_GBP=("Battery_Savings_GBP", "sum"),
            Electricity_Purchase_Cost_GBP=(
                "Electricity_Purchase_Cost_GBP", "sum"
            ),
            Incremental_Cashflow_GBP=(
                "Incremental_Cashflow_GBP", "sum"
            )
        )

        annual_financials["Cumulative_Cashflow_GBP"] = (
            annual_financials["Incremental_Cashflow_GBP"].cumsum()
        )

        annual_financials["Cumulative_Net_Cashflow_GBP"] = (
            annual_financials["Cumulative_Cashflow_GBP"]
            - total_capex_value
        )

        # --------------------------------------
        # 9. ROI AND BREAK-EVEN
        # --------------------------------------

        if total_capex_value > 0:

            roi = net_profit / total_capex_value * 100

            reached = annual_financials[
                annual_financials["Cumulative_Net_Cashflow_GBP"] >= 0
            ]

            break_even_year = (
                int(reached.iloc[0]["Year"])
                if not reached.empty
                else "Not reached"
            )

        else:
            roi = np.nan
            break_even_year = "No investment"

        bep_roi = pd.DataFrame({
            "Metric": [
                "Total Investment CAPEX",
                "Hydrogen Revenue",
                "Battery Savings",
                "Total Incremental Cash Flow",
                "Net Investment Profit",
                "ROI (%)",
                "Break-Even Year"
            ],
            "Value": [
                total_capex_value,
                total_hydrogen_revenue,
                total_battery_savings,
                total_incremental_cashflow,
                net_profit,
                roi,
                break_even_year
            ]
        })

        # --------------------------------------
        # 10. EXPORT AND FORMAT EXCEL
        # --------------------------------------

        output_file = "Tier1_Investment_ROI_BEP_Analysis.xlsx"

        with pd.ExcelWriter(
            output_file, engine="openpyxl"
        ) as writer:

            sheets = {
                "Investment Summary": investment_summary,
                "Daily Operations": daily,
                "Annual Operations": annual_operations,
                "Annual Financials": annual_financials,
                "BEP ROI Analysis": bep_roi
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

        print("\n========== TIER 1 RESULTS ==========")

        print(f"Battery Installation: {battery_MW:,.2f} MW")
        print(f"Battery Storage Capacity: {battery_MWh:,.2f} MWh")
        print(f"Hydrogen Installation: {hydrogen_MW:,.2f} MW")

        print(f"\nBattery Charged: {total_battery_charge:,.2f} MWh")
        print(f"Battery Discharged: {total_battery_discharge:,.2f} MWh")
        print(f"Maximum Battery Stored: {max_battery_stored:,.2f} MWh")

        print(f"\nHydrogen Produced: {total_hydrogen_produced:,.2f} kg")
        print(f"Hydrogen Sold: {total_hydrogen_sold:,.2f} kg")

        print(f"\nSurplus Captured: {captured_surplus:,.2f} MWh")
        print(f"Surplus Capture Rate: {capture_rate:,.2f}%")
        print(f"Electricity Curtailed: {total_curtailed:,.2f} MWh")
        print(f"Electricity Purchased: {total_electricity_purchased:,.2f} MWh")

        print(f"\nTotal CAPEX: £{total_capex_value:,.2f}")
        print(f"Hydrogen Revenue: £{total_hydrogen_revenue:,.2f}")
        print(f"Battery Savings: £{total_battery_savings:,.2f}")
        print(f"Net Investment Profit: £{net_profit:,.2f}")
        print(f"ROI: {roi:,.2f}%")
        print(f"Break-Even Year: {break_even_year}")

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

        print("\n===== OPERATIONS =====")

        total_hydrogen_MWh = sum(
            prob.getSolution(hydrogen_electricity[t])
            for t in range(number_days)
        )

        total_purchase_MWh = sum(
            prob.getSolution(electricity_purchase[t])
            for t in range(number_days)
        )

        total_charge_MWh = sum(
            prob.getSolution(battery_charge[t])
            for t in range(number_days)
        )

        total_discharge_MWh = sum(
            prob.getSolution(battery_discharge[t])
            for t in range(number_days)
        )

        print(f"Hydrogen Electricity: {total_hydrogen_MWh:,.2f} MWh")
        print(f"Electricity Purchased: {total_purchase_MWh:,.2f} MWh")
        print(f"Battery Charging: {total_charge_MWh:,.2f} MWh")
        print(f"Battery Discharging: {total_discharge_MWh:,.2f} MWh")

    else:
        print("No optimal solution available.")

