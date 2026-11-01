"""Render M5 presentation assets from committed evidence; no ML execution.

Run locally: python scripts/presentation_figures.py (requires matplotlib).
"""
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/figures/m5"


def main():
    evidence = json.loads((ROOT / "docs/m3-evidence.json").read_text())
    results = evidence["searches"]["results"]
    OUT.mkdir(parents=True, exist_ok=True)
    m1 = json.loads((ROOT / "docs/m1-evidence.json").read_text())
    baselines = {r["task"]: r["record"] for k in ("classification", "segmentation") for r in m1[k]["results"]}
    rows = []
    for r in results:
        v = r["validation"]
        baseline = baselines[r["task"]]
        assert baseline["run_id"] == r["reference_run"]
        assert baseline["best_validation"]["primary"] == r["reference_primary"]
        assert v["full_split"] and v["primary"] == r["selected_primary"]
        selected = next(t for t in r["trials"] if t["run_id"] == r["selected_run"])
        assert selected["full_validation"] and selected["primary"] == r["selected_primary"]
        assert r["reload"]["passed"] and r["reload"]["primary_delta"] == 0
        rows.append(dict(task=r["task"], metric=v["primary_name"],
                         baseline=r["reference_primary"], selected=r["selected_primary"],
                         gain_pp=100*(r["selected_primary"]-r["reference_primary"]),
                         images=v["images"], scored_items=v["count"],
                         reference_run=r["reference_run"], selected_run=r["selected_run"],
                         selected_source=selected["source_commit"], seed=selected["seed"]))
    with (OUT / "validation-comparison.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "svg.fonttype": "none", "axes.spines.top": False,
                         "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    for ax, group, title in zip(axes, (rows[:2], rows[2:]),
                               ("Classification Â· accuracy (%)", "Segmentation Â· macro IoU (%)")):
        for i, row in enumerate(group):
            for offset, key, color in ((-.18, "baseline", "#9ba9b7"), (.18, "selected", "#137c83")):
                val = row[key]*100
                ax.bar(i+offset, val, .32, color=color, label=key.title() if i == 0 else None)
                ax.text(i+offset, val+1.5, f"{val:.2f}", ha="center", fontsize=10)
            ax.text(i, 112, f"+{row['gain_pp']:.2f} pp", ha="center", color="#137c83", weight="bold")
        ax.set_xticks(range(2), [r["task"].removeprefix("m-") for r in group])
        ax.set_ylim(0, 120)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.set_title(title, pad=12)
        ax.legend(loc="lower right", frameon=True, facecolor="white", framealpha=1)
    fig.suptitle("Full validation: frozen reference â†’ retained pipeline", fontsize=16)
    fig.text(.5, .035, "Seed 2026 Â· provisional Â· different recipes/pretraining Â· official test scores pending", ha="center", fontsize=10)
    fig.tight_layout(rect=(0, .08, 1, .94))
    for ext in ("svg", "png"):
        fig.savefig(OUT / f"validation-comparison.{ext}", dpi=180)
    plt.close(fig)
    pv = next(r for r in results if r["task"] == "m-pv4ger-seg")
    screens = [t for t in pv["trials"] if t["recipe"]["phase"] == "screen"]
    scores = [pv["reference_primary"], screens[0]["primary"], screens[1]["primary"], pv["selected_primary"]]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.barh(range(4), [s*100 for s in scores], color=["#9ba9b7", "#137c83", "#b9c3cd", "#137c83"])
    ax.set_yticks(range(4), ["Frozen M1 reference", "FCN pretrained Â· screen", "DeepLab Mobile Â· screen", "FCN pretrained Â· final: KEEP"])
    ax.invert_yaxis()
    ax.set_xlim(0, 105)
    ax.set_xlabel("Full-validation macro IoU (%)")
    for i, score in enumerate(scores):
        ax.text(score*100+1, i, f"{score*100:.2f}", va="center")
    ax.set_title("PV4GER-Seg: compare screens, invest in FCN, retain final", pad=15)
    fig.text(.5, .025, "Screening informs the next experiment; only the final trial promotes. Single seed; no causal claim.", ha="center", fontsize=10)
    fig.tight_layout(rect=(0, .07, 1, 1))
    for ext in ("svg", "png"):
        fig.savefig(OUT / f"experiment-decision.{ext}", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
