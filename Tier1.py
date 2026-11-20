import xpress as xp
import pandas as pd
import numpy as np

# Create a problem called Tier1
prob = xp.problem(name='Tier1')

#Import the data from the csv file
raw_data_df=pd.read_excel("C:\\Users\\gonza\\OneDrive - University of Edinburgh\\MMCS\\Python\\Project\\Data\\surplus_deficit_with_after_imputation.xlsx")
demand_list = raw_data_df['demand'].tolist()
total_generation_list = raw_data_df['total_MW'].tolist()
market_price_list = raw_data_df['avg_price_£_per_MWh_after_imputation'].tolist()


#Other parameters
battery_cost=240374.88/10
hydrogen_costs=20000000/20
hydrogen_selling_price=9.5

hydrogen_yield=55.9
number_days = len(raw_data_df)
#electricity_purchase_price=800
electricity_purchase_price=[abs(market_price_list[t]*10.5) for t in range(number_days)]

#Make dataframes list for efficiency


#Create decision variables
battery_installation_DV=prob.addVariable('battery_installation')
hydrogen_installation_DV=prob.addVariable('hydrogen_installation')

max_hydrogen_capacity=100000

electricity_store_amount=xp.array([prob.addVariable(name='electricity_store_amount_{0}'.format(i+1))
                             for i in range(number_days)],dtype='O').reshape(number_days)
stored_electricity_amount=xp.array([prob.addVariable(name='stored_electricity_amount_{0}'.format(i+1))
                             for i in range(number_days)],dtype='O').reshape(number_days)
curtailed_electricity=xp.array([prob.addVariable(name='curtailed_electricity_{0}'.format(i+1))
                             for i in range(number_days)],dtype='O').reshape(number_days)
electricity_for_hydrogen=xp.array([prob.addVariable(name='electricity_for_hydrogen_{0}'.format(i+1))
                             for i in range(number_days)],dtype='O').reshape(number_days)
use_from_battery=xp.array([prob.addVariable(name='use_from_battery_{0}'.format(i+1))
                             for i in range(number_days)],dtype='O').reshape(number_days)
sell_electricity=xp.array([prob.addVariable(name='sell_electricity_{0}'.format(i+1))
                             for i in range(number_days)],dtype='O').reshape(number_days)
buy_electricity=xp.array([prob.addVariable(name='buy_electricity_{0}'.format(i+1))
                             for i in range(number_days)],dtype='O').reshape(number_days)
produce_hydrogen=xp.array([prob.addVariable(vartype=xp.binary, name='produce_hydrogen_{0}'.format(i+1))
                             for i in range(number_days)]).reshape(number_days)

#Constraints
#All electricity must be accounted for
daily_electricity_balance=[
    total_generation_list[t]+use_from_battery[t]+buy_electricity[t]==
    demand_list[t]+electricity_for_hydrogen[t]+electricity_store_amount[t] + curtailed_electricity[t]
    for t in range(number_days)
    ]
#Demand must be met
demand_constraint=[
    sell_electricity[t]<=demand_list[t]
    for t in range(number_days)
]
prob.addConstraint(demand_constraint)
#Energy stored constraint, we assume that the batteries star with the minimum 20% charge
energy_stored_balanced = [
    stored_electricity_amount[t] == 0.2*battery_installation_DV if t == 0 else
    stored_electricity_amount[t] == stored_electricity_amount[t-1]
        + 0.9 * electricity_store_amount[t-1]
        - use_from_battery[t-1]
    for t in range(number_days)
]
#test
prob.addConstraint(battery_installation_DV==2000)

#Hydrogen generation capacity constraints
hydrogen_generation_20P=[
    electricity_for_hydrogen[t]>=0.2*hydrogen_installation_DV-(1-produce_hydrogen[t])*max_hydrogen_capacity 
    for t in range(number_days)
]
hydrogen_generation_100P=[
    electricity_for_hydrogen[t]<=hydrogen_installation_DV
    for t in range(number_days)    
]

#Battery storage optimal range constraints
battery_storage_20P=[stored_electricity_amount[t]>=0.2*battery_installation_DV for t in range(number_days)]
battery_storage_80P=[stored_electricity_amount[t]<=0.8*battery_installation_DV for t in range(number_days)]


#Objective function
infrastructure_costs=battery_installation_DV*battery_cost + hydrogen_installation_DV*hydrogen_costs
operating_profits=xp.Sum(
    market_price_list[t]*sell_electricity[t] + produce_hydrogen[t]*hydrogen_selling_price/hydrogen_yield
    for t in range(number_days)
)
operating_costs=xp.Sum(
    buy_electricity[t]*electricity_purchase_price[t]
    for t in range(number_days)
)

total_profit=operating_profits-infrastructure_costs-operating_costs

prob.setObjective(total_profit,sense=xp.maximize)
prob.addConstraint(
    daily_electricity_balance, energy_stored_balanced, hydrogen_generation_100P, 
    hydrogen_generation_20P,battery_storage_20P, battery_storage_80P
)

prob.writeProb ("problem","lp")
prob.solve()

print(prob.attributes.objval)

result_df=pd.DataFrame({
    'Date':raw_data_df['date'],
    'Production':total_generation_list,
    'Demand':demand_list,
    'Avg_price_per_MWh':market_price_list,
    'Electricity_sold':prob.getSolution(sell_electricity),
    'Electricity_bought':prob.getSolution(buy_electricity),
    'Electricity_to_store':prob.getSolution(electricity_store_amount),
    'Curtailment':prob.getSolution(curtailed_electricity),
    'stored_electricity':prob.getSolution(stored_electricity_amount),
    'Electricity_for_Hydrogen':prob.getSolution(electricity_for_hydrogen),
    'Electricity_from_batteries':prob.getSolution(use_from_battery)
})

result_df.to_excel('results.xlsx',sheet_name='Results',index=False)