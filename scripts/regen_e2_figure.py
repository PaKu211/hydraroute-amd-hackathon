import json, sys

sys.path.insert(0, ".")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Honest E2 values (recomputed from measured routing, frontier pricing)
labels = ["Always-Small", "HydraRoute\n(measured)", "Always-Large"]
costs = [0.0015, 0.2305, 0.1310]
colors = ["#55A868", "#C44E52", "#4C72B0"]

fig, ax = plt.subplots(figsize=(4.2, 3.0))
bars = ax.bar(labels, costs, color=colors, width=0.6)
ax.set_ylabel("Cost per 67 tasks (USD)")
ax.set_title("Frontier pricing: measured routing")
for b, c in zip(bars, costs):
    ax.text(
        b.get_x() + b.get_width() / 2,
        c + 0.004,
        f"${c:.4f}",
        ha="center",
        va="bottom",
        fontsize=8,
    )
ax.set_ylim(0, max(costs) * 1.18)
fig.tight_layout()
fig.savefig("figures/e2_cost_frontier.png", dpi=150)
print("wrote figures/e2_cost_frontier.png")
