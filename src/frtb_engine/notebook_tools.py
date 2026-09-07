"""Small presentation helpers used by the educational notebooks."""

from __future__ import annotations

from collections.abc import Iterable

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd


INR_CRORE = 10_000_000.0


def configure_notebooks() -> None:
    """Use readable tables and charts without scientific notation."""
    pd.set_option("display.max_columns", 30)
    pd.set_option("display.max_rows", 60)
    pd.set_option("display.width", 160)
    pd.set_option("display.float_format", lambda value: f"{value:,.4f}")
    plt.rcParams.update({
        "figure.figsize": (10, 4.8),
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.alpha": 0.20,
        "font.size": 10,
    })


def crore_table(frame: pd.DataFrame, money_columns: Iterable[str]) -> pd.DataFrame:
    """Return a display copy with INR values expressed in crore."""
    shown = frame.copy()
    rename = {}
    for column in money_columns:
        if column in shown.columns:
            shown[column] = shown[column] / INR_CRORE
            if column == "raw_sensitivity":
                rename[column] = "Raw Sensitivity (INR crore per unit change)"
            else:
                readable = column.replace("_inr", "").replace("_", " ").title()
                rename[column] = f"{readable} (INR crore)"
    return shown.rename(columns=rename)


def percent_columns(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    """Return a display copy with decimal rates expressed as percentages."""
    shown = frame.copy()
    rename = {}
    for column in columns:
        if column in shown.columns:
            shown[column] = shown[column] * 100.0
            rename[column] = f"{column.replace('_', ' ').title()} (%)"
    return shown.rename(columns=rename)


def draw_flow(labels: list[str], title: str, wrap_after: int = 6) -> None:
    """Draw a compact left-to-right calculation chain, wrapping long chains."""
    rows = int(np.ceil(len(labels) / wrap_after))
    fig, ax = plt.subplots(figsize=(12, max(2.3, rows * 2.0)))
    ax.set_xlim(0, wrap_after)
    ax.set_ylim(0, rows)
    ax.axis("off")
    positions = []
    for index, label in enumerate(labels):
        row = index // wrap_after
        offset = index % wrap_after
        column = offset if row % 2 == 0 else wrap_after - offset - 1
        y = rows - row - 0.62
        x = column + 0.08
        positions.append((x, y, row))
        box = FancyBboxPatch(
            (x, y), 0.82, 0.42,
            boxstyle="round,pad=0.04,rounding_size=0.04",
            facecolor="#E8F1FB", edgecolor="#276FBF", linewidth=1.2,
        )
        ax.add_patch(box)
        ax.text(x + 0.41, y + 0.21, label, ha="center", va="center", fontsize=9, wrap=True)
    for index in range(len(positions) - 1):
        x, y, row = positions[index]
        nx, ny, next_row = positions[index + 1]
        if next_row == row and nx > x:
            start, end = (x + 0.88, y + 0.21), (nx - 0.06, ny + 0.21)
        elif next_row == row:
            start, end = (x + 0.02, y + 0.21), (nx + 0.88, ny + 0.21)
        else:
            start, end = (x + 0.41, y - 0.04), (nx + 0.41, ny + 0.48)
        ax.annotate("", xy=end, xytext=start, arrowprops={"arrowstyle": "->", "color": "#555555"})
    ax.set_title(title, loc="left", fontsize=14, weight="bold")
    plt.tight_layout()
    plt.show()


def bar_crore(series: pd.Series, title: str, axis_label: str = "INR crore", color: str = "#276FBF") -> None:
    """Plot named INR amounts after converting them to crore."""
    values = series.astype(float) / INR_CRORE
    ax = values.plot(kind="bar", color=color)
    ax.set_title(title, loc="left", weight="bold")
    ax.set_ylabel(axis_label)
    ax.set_xlabel("")
    ax.tick_params(axis="x", rotation=35)
    for patch, value in zip(ax.patches, values):
        ax.text(patch.get_x() + patch.get_width() / 2, patch.get_height(), f"{value:,.2f}", ha="center", va="bottom", fontsize=8)
    plt.tight_layout()
    plt.show()


def bar_inr(
    series: pd.Series,
    title: str,
    color: str = "#276FBF",
    x_axis_label: str = "",
    y_axis_label: str = "INR",
) -> None:
    """Plot smaller INR amounts in full rather than scientific notation."""
    values = series.astype(float)
    ax = values.plot(kind="bar", color=color)
    ax.set_title(title, loc="left", weight="bold")
    ax.set_ylabel(y_axis_label)
    ax.set_xlabel(x_axis_label)
    ax.ticklabel_format(axis="y", style="plain", useOffset=False)
    ax.tick_params(axis="x", rotation=35)
    for patch, value in zip(ax.patches, values):
        vertical = "bottom" if value >= 0 else "top"
        ax.text(patch.get_x() + patch.get_width() / 2, value, f"{value:,.0f}", ha="center", va=vertical, fontsize=8)
    plt.tight_layout()
    plt.show()


def draw_capital_map() -> None:
    """Show the seven SBM classes and the parallel capital components."""
    classes = ["GIRR", "CSR non-sec", "CSR sec non-CTP", "CSR sec CTP", "Equity", "Commodity", "FX"]
    fig, ax = plt.subplots(figsize=(12, 5.6))
    ax.set_xlim(0, 12); ax.set_ylim(0, 8); ax.axis("off")
    for row, label in enumerate(classes):
        y = 7.1 - row
        box = FancyBboxPatch((0.3, y), 2.0, 0.55, boxstyle="round,pad=0.03", facecolor="#E8F1FB", edgecolor="#276FBF")
        ax.add_patch(box); ax.text(1.3, y + 0.275, label, ha="center", va="center", fontsize=9)
        ax.annotate("", xy=(4.0, 4.2), xytext=(2.3, y + 0.275), arrowprops={"arrowstyle":"->", "color":"#777777", "alpha":0.65})
    nodes = [(4.0,3.65,"SBM"),(4.0,2.2,"DRC"),(4.0,0.75,"RRAO"),(7.1,2.2,"SA capital"),(9.8,2.2,"Market RWA")]
    for x,y,label in nodes:
        box = FancyBboxPatch((x,y),1.7,0.7,boxstyle="round,pad=0.04",facecolor="#FFF2CC",edgecolor="#B8860B",linewidth=1.2)
        ax.add_patch(box); ax.text(x+0.85,y+0.35,label,ha="center",va="center",weight="bold")
    for y in (4.0,2.55,1.1):
        ax.annotate("",xy=(7.1,2.55),xytext=(5.7,y),arrowprops={"arrowstyle":"->","color":"#555555"})
    ax.annotate("",xy=(9.8,2.55),xytext=(8.8,2.55),arrowprops={"arrowstyle":"->","color":"#555555"})
    ax.text(9.3,2.78,"x 12.5",ha="center",fontsize=9)
    ax.set_title("How the Standardised Approach components join together",loc="left",fontsize=14,weight="bold")
    plt.tight_layout(); plt.show()


def heatmap(frame: pd.DataFrame, title: str, value_format: str = ".2f") -> None:
    """Draw a labelled matrix for correlations or capital components."""
    values = frame.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(max(6, frame.shape[1] * 0.75), max(3.5, frame.shape[0] * 0.55)))
    image = ax.imshow(values, cmap="Blues", aspect="auto")
    ax.set_xticks(range(frame.shape[1]), frame.columns, rotation=40, ha="right")
    ax.set_yticks(range(frame.shape[0]), frame.index)
    for row in range(frame.shape[0]):
        for column in range(frame.shape[1]):
            ax.text(column, row, format(values[row, column], value_format), ha="center", va="center", fontsize=8)
    ax.set_title(title, loc="left", weight="bold")
    fig.colorbar(image, ax=ax, shrink=0.8)
    plt.tight_layout()
    plt.show()
