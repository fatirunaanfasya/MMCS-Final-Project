
import xpress as xp

# -----------------------------
# Scenario data
# -----------------------------

scenarios = ["High", "Medium", "Low"]

probability = {
    "High": 0.3,
    "Medium": 0.4,
    "Low": 0.3
}

operating_profit = {
    "High": 100,
    "Medium": 60,
    "Low": -20
}

investment_cost = 50

# -----------------------------
# Risk parameters
# -----------------------------

alpha = 0.80
lambda_ = 0.50

# -----------------------------
# Create model
# -----------------------------

model = xp.problem("Mean_CVaR")

# First-stage variable
x = xp.var(lb=0, ub=10, name="battery_capacity")

# Second-stage variables
y = {
    s: xp.var(lb=0, name=f"operation_{s}")
    for s in scenarios
}

# CVaR auxiliary variables
eta = xp.var(name="eta")

z = {
    s: xp.var(lb=0, name=f"z_{s}")
    for s in scenarios
}

# Add variables
model.addVariable(x)
model.addVariable(list(y.values()))
model.addVariable(eta)
model.addVariable(list(z.values()))

# -----------------------------
# Scenario profits
# -----------------------------

profit = {
    s: operating_profit[s] * y[s]
       - investment_cost * x
    for s in scenarios
}

# -----------------------------
# Constraints
# -----------------------------

for s in scenarios:

    # Cannot operate more capacity than installed
    model.addConstraint(y[s] <= x)

    # CVaR shortfall constraint
    model.addConstraint(z[s] >= eta - profit[s])

# -----------------------------
# Expected profit
# -----------------------------

expected_profit = xp.Sum(
    probability[s] * profit[s]
    for s in scenarios
)

# -----------------------------
# CVaR
# -----------------------------

cvar = eta - (1 / (1 - alpha)) * xp.Sum(
    probability[s] * z[s]
    for s in scenarios
)

# -----------------------------
# Mean-CVaR objective
# -----------------------------

objective = (
    (1 - lambda_) * expected_profit
    + lambda_ * cvar
)

model.setObjective(objective, sense=xp.maximize)

# -----------------------------
# Solve
# -----------------------------

model.solve()

# -----------------------------
# Results
# -----------------------------

print("Battery capacity:", x.solution_value)

print("Expected profit:", expected_profit.value())

print("CVaR:", cvar.value())

print("Objective:", objective.value())

for s in scenarios:
    print(
        s,
        "Operation:", y[s].solution_value,
        "Profit:", profit[s].value()
    )
