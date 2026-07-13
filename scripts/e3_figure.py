import json, os
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

EXP = "/home/smiley/projek/agy/hackathon-lablab/experiments"
FIG = "/home/smiley/projek/agy/hackathon-lablab/figures"
os.makedirs(FIG, exist_ok=True)

d7 = json.load(open(f"{EXP}/e3_qwen7b.json"))["aggregate"]
d05 = json.load(open(f"{EXP}/e3_qwen05b.json"))["aggregate"]

tiers = ["Qwen2.5-0.5B\n(small tier)", "Qwen2.5-7B\n(large tier)"]
mean_lat = [d05["mean_latency_s"], d7["mean_latency_s"]]
p50 = [d05["p50_latency_s"], d7["p50_latency_s"]]
p95 = [d05["p95_latency_s"], d7["p95_latency_s"]]
tput = [d05["throughput_tok_s"], d7["throughput_tok_s"]]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 3.4))

x = range(len(tiers))
w = 0.26
ax1.bar([i - w for i in x], p50, w, label="p50", color="#4C72B0")
ax1.bar([i for i in x], mean_lat, w, label="mean", color="#DD8452")
ax1.bar([i + w for i in x], p95, w, label="p95", color="#55A868")
ax1.set_xticks(list(x))
ax1.set_xticklabels(tiers)
ax1.set_ylabel("Latency (s / request)")
ax1.set_title("Serving latency (vLLM, RTX PRO 6000)")
ax1.legend(fontsize=8)

ax2.bar(x, tput, color=["#55A868", "#4C72B0"])
ax2.set_xticks(list(x))
ax2.set_xticklabels(tiers)
ax2.set_ylabel("Throughput (tok/s)")
ax2.set_title("Serving throughput")
for i, v in enumerate(tput):
    ax2.text(i, v + 4, f"{v:.0f}", ha="center", fontsize=8)

fig.tight_layout()
fig.savefig(f"{FIG}/e3_latency_throughput.png", dpi=150)
print("wrote e3_latency_throughput.png")

# Cost-per-1k-requests extrapolation at frontier prices for the paper's 67-task mix
in_price, out_price = 10.0, 30.0  # $/M tokens (GPT-4-class frontier, from E2)
cost7 = (
    d7["sum_prompt_tokens"] * in_price + d7["sum_completion_tokens"] * out_price
) / 1000
cost05 = (
    d05["sum_prompt_tokens"] * in_price + d05["sum_completion_tokens"] * out_price
) / 1000
fig2, ax = plt.subplots(figsize=(4.6, 3.2))
ax.bar(x, [cost05, cost7], color=["#55A868", "#4C72B0"])
ax.set_xticks(list(x))
ax.set_xticklabels(tiers)
ax.set_ylabel("Cost for 67 tasks ($)")
ax.set_title("Frontier-price tier cost (E2 model)")
for i, v in enumerate([cost05, cost7]):
    ax.text(i, v + 0.02, f"${v:.3f}", ha="center", fontsize=8)
fig2.tight_layout()
fig2.savefig(f"{FIG}/e3_tier_cost.png", dpi=150)
print("wrote e3_tier_cost.png", round(cost05, 4), round(cost7, 4))
