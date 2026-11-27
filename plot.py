
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_excel("test.xlsx")

plt.figure(figsize=(11, 7))

markers = ['o', 's', '^', 'D', 'v', 'P', 'X']

alphas = sorted(df["alpha"].unique())
lambdas = sorted(df["lambda"].unique())

for i, alpha in enumerate(alphas):

    subset = df[df["alpha"] == alpha]

    plt.scatter(
        subset["expected_profit"],
        subset["cvar"],
        c=subset["lambda"],
        cmap="viridis",
        vmin=min(lambdas),
        vmax=max(lambdas),
        marker=markers[i % len(markers)],
        s=80,
        label=f"Alpha = {alpha}"
    )

plt.xlabel("Expected Profit (£)")
plt.ylabel("CVaR (£)")
plt.title("Expected Profit vs CVaR")

# Colour represents Lambda
sm = plt.cm.ScalarMappable(
    cmap="viridis",
    norm=plt.Normalize(min(lambdas), max(lambdas))
)
sm.set_array([])

plt.colorbar(sm, ax=plt.gca(), label="Lambda")

# Marker shape represents Alpha
plt.legend(title="Confidence level (Alpha)")

plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()
