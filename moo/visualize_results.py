import os
import re
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np
from itertools import combinations

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

OBJECTIVES = ["co2e", "hnv", "protein", "hwp"]
LABELS = {
    "co2e": "Net Zero CO2e",
    "hnv": "Biodiversity (HNV)",
    "protein": "Protein Output",
    "hwp": "Harvested Wood Products",
}


def load_all_generations() -> dict[int, pd.DataFrame]:
    pattern = re.compile(r"gen(\d+)_pareto\.csv$")
    generations = {}
    for fname in os.listdir(RESULTS_DIR):
        m = pattern.match(fname)
        if m:
            gen = int(m.group(1))
            df = pd.read_csv(os.path.join(RESULTS_DIR, fname), usecols=OBJECTIVES)
            generations[gen] = df
    return dict(sorted(generations.items()))


def plot_final_pareto(df: pd.DataFrame, generation: int) -> None:
    pairs = list(combinations(OBJECTIVES, 2))
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    fig.suptitle(f"Pareto Front — Generation {generation}", fontsize=14)

    for ax, (x_col, y_col) in zip(axes.flat, pairs):
        ax.scatter(df[x_col], df[y_col], s=30, alpha=0.7, edgecolors="none")
        ax.set_xlabel(LABELS[x_col], fontsize=9)
        ax.set_ylabel(LABELS[y_col], fontsize=9)
        ax.ticklabel_format(style="sci", axis="both", scilimits=(0, 0))

    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, f"pareto_gen{generation}.png"), dpi=150)
    plt.show()


def plot_evolution(generations: dict[int, pd.DataFrame]) -> None:
    gen_numbers = sorted(generations.keys())
    colors = cm.viridis(np.linspace(0, 1, len(gen_numbers)))
    color_map = {g: c for g, c in zip(gen_numbers, colors)}

    pairs = list(combinations(OBJECTIVES, 2))
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    fig.suptitle("Pareto Front Evolution Across Generations", fontsize=14)

    all_axes = axes.flatten().tolist()
    for ax, (x_col, y_col) in zip(all_axes, pairs):
        for gen in gen_numbers:
            df = generations[gen]
            ax.scatter(
                df[x_col], df[y_col],
                s=10, alpha=0.4,
                color=color_map[gen],
                edgecolors="none",
            )
        ax.set_xlabel(LABELS[x_col], fontsize=9)
        ax.set_ylabel(LABELS[y_col], fontsize=9)
        ax.ticklabel_format(style="sci", axis="both", scilimits=(0, 0))

    sm = cm.ScalarMappable(
        cmap="viridis",
        norm=plt.Normalize(vmin=min(gen_numbers), vmax=max(gen_numbers)),
    )
    sm.set_array([])
    fig.colorbar(sm, ax=all_axes, label="Generation", shrink=0.6, pad=0.02)

    plt.savefig(os.path.join(RESULTS_DIR, "pareto_evolution.png"), dpi=150)
    plt.show()


def plot_parallel_coordinates(df: pd.DataFrame, generation: int) -> None:
    normed = (df[OBJECTIVES] - df[OBJECTIVES].min()) / (
        df[OBJECTIVES].max() - df[OBJECTIVES].min()
    )

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.suptitle(
        f"Parallel Coordinates — Generation {generation} Pareto Front", fontsize=14
    )

    x_positions = range(len(OBJECTIVES))
    colors = cm.plasma(np.linspace(0, 1, len(df)))

    for i, (_, row) in enumerate(normed.iterrows()):
        ax.plot(x_positions, row[OBJECTIVES].values, color=colors[i], alpha=0.4, lw=1)

    ax.set_xticks(list(x_positions))
    ax.set_xticklabels([LABELS[o] for o in OBJECTIVES], fontsize=10)
    ax.set_ylabel("Normalised objective value", fontsize=10)
    ax.set_ylim(0, 1)
    ax.grid(axis="x", linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(
        os.path.join(RESULTS_DIR, f"parallel_coords_gen{generation}.png"), dpi=150
    )
    plt.show()


def _hv_dominates(p: list, q: list) -> bool:
    """Return True if p strictly dominates q in a minimization sense."""
    return all(p[i] <= q[i] for i in range(len(p))) and any(p[i] < q[i] for i in range(len(p)))


def _hv_update_nd(nd_set: list, point: list) -> list:
    """Add point to nd_set while maintaining non-dominance. Returns updated set."""
    for p in nd_set:
        if _hv_dominates(p, point) or p == point:
            return nd_set
    return [p for p in nd_set if not _hv_dominates(point, p)] + [point]


def _hv_recursive(points: list, ref: list) -> float:
    """
    WFG slice hypervolume algorithm (minimization).
    Sorts by last objective, slices into layers, recurses on projected non-dominated sets.
    """
    if not points:
        return 0.0

    d = len(ref)
    if d == 1:
        return ref[0] - min(p[0] for p in points)

    pts_sorted = sorted(points, key=lambda p: p[-1])  # ascending last dim

    hv = 0.0
    nd_projected: list = []

    for i, p in enumerate(pts_sorted):
        nd_projected = _hv_update_nd(nd_projected, p[:-1])
        next_val = pts_sorted[i + 1][-1] if i + 1 < len(pts_sorted) else ref[-1]
        height = next_val - p[-1]
        if height > 0:
            hv += height * _hv_recursive(nd_projected, ref[:-1])

    return hv


def compute_hypervolume(df: pd.DataFrame, ref_point: list[float]) -> float:
    """
    Compute the hypervolume indicator for a Pareto front (minimization, normalised space).
    Points that exceed the reference in any objective are excluded.
    """
    pts = df[OBJECTIVES].values.tolist()
    valid = [p for p in pts if all(p[i] <= ref_point[i] for i in range(len(ref_point)))]
    if not valid:
        return 0.0
    return _hv_recursive(valid, ref_point)


def plot_hypervolume(generations: dict[int, pd.DataFrame]) -> None:
    # Normalise objectives to [0, 1] using global min/max so the HV is not
    # dominated by whichever objective happens to have the largest absolute scale.
    all_data = pd.concat(generations.values())
    g_min = all_data[OBJECTIVES].min()
    g_max = all_data[OBJECTIVES].max()
    g_range = g_max - g_min

    def normalise(df: pd.DataFrame) -> pd.DataFrame:
        return (df[OBJECTIVES] - g_min) / g_range

    # Reference point slightly beyond the worst observed value in normalised space
    ref_point = [1.1] * len(OBJECTIVES)

    gen_numbers = sorted(generations.keys())
    print("Computing hypervolume per generation…")
    hvs = []
    for gen in gen_numbers:
        hv = compute_hypervolume(normalise(generations[gen]), ref_point)
        hvs.append(hv)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(gen_numbers, hvs, marker="o", markersize=3, linewidth=1.5, color="steelblue")
    ax.fill_between(gen_numbers, hvs, alpha=0.15, color="steelblue")
    ax.set_xlabel("Generation")
    ax.set_ylabel("Hypervolume Indicator (normalised objectives)")
    ax.set_title("Hypervolume Indicator Over Generations")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "hypervolume.png"), dpi=150)
    plt.show()


def plot_gen100_pareto(generations: dict[int, pd.DataFrame], target_gen: int = 100) -> None:
    if target_gen not in generations:
        print(f"Generation {target_gen} not found in results.")
        return

    df = generations[target_gen]
    d = len(OBJECTIVES)
    fig, axes = plt.subplots(d, d, figsize=(14, 13))
    fig.suptitle(f"Pareto Front — Generation {target_gen}  ({len(df)} solutions)", fontsize=14)

    for row in range(d):
        for col in range(d):
            ax = axes[row, col]
            if row == col:
                ax.hist(df[OBJECTIVES[row]], bins=20, color="steelblue", edgecolor="white", linewidth=0.4)
                ax.set_xlabel(LABELS[OBJECTIVES[col]], fontsize=8)
                ax.ticklabel_format(style="sci", axis="x", scilimits=(0, 0))
                ax.set_yticks([])
            elif row > col:
                ax.scatter(df[OBJECTIVES[col]], df[OBJECTIVES[row]], s=18, alpha=0.7,
                           color="steelblue", edgecolors="none")
                ax.set_xlabel(LABELS[OBJECTIVES[col]], fontsize=8)
                ax.set_ylabel(LABELS[OBJECTIVES[row]], fontsize=8)
                ax.ticklabel_format(style="sci", axis="both", scilimits=(0, 0))
            else:
                ax.set_visible(False)

    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, f"pareto_gen{target_gen}_matrix.png"), dpi=150)
    plt.show()


def plot_population_size(generations: dict[int, pd.DataFrame]) -> None:
    gen_numbers = sorted(generations.keys())
    sizes = [len(generations[g]) for g in gen_numbers]

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(gen_numbers, sizes, marker="o", markersize=3, linewidth=1)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Pareto Front Size (solutions)")
    ax.set_title("Pareto Front Size Over Generations")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "pareto_front_size.png"), dpi=150)
    plt.show()


def main() -> None:
    generations = load_all_generations()
    if not generations:
        print(f"No generation CSV files found in {RESULTS_DIR}")
        return

    final_gen = max(generations.keys())
    print(f"Loaded {len(generations)} generations (1–{final_gen})")
    print(f"Final generation has {len(generations[final_gen])} Pareto-optimal solutions")

    plot_final_pareto(generations[final_gen], final_gen)
    plot_gen100_pareto(generations)
    plot_parallel_coordinates(generations[final_gen], final_gen)
    plot_evolution(generations)
    plot_population_size(generations)
    plot_hypervolume(generations)


if __name__ == "__main__":
    main()
