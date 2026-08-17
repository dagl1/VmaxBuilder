from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from itertools import cycle
from typing import Any

from plotly import graph_objects as go

from VmaxBuilder.utils.plotting.colors import (
    blend_hex_color_sequence,
    custom_colorblind_color_discrete_palette,
)
from VmaxBuilder.utils.plotting.config import PlotConfig


def prepare_alluvial_data(
    category_participation_dict: Mapping[str, Mapping[str, Iterable[str]]],
    *,
    category_order: Sequence[str] | None = None,
    missing_label: str = "unassigned",
) -> dict[str, Any]:
    """Generated: validation needed.

    Description:
        Convert category-to-label membership mapping into Parcats-ready data.

    Args:
        category_participation_dict (Mapping[str, Mapping[str, Iterable[str]]]):
            Category mapping where each category points to labels and each label
            points to member identifiers.
        category_order (Sequence[str] | None): Explicit category order for
            resulting dimensions. Defaults to insertion order from
            ``category_participation_dict``.
        missing_label (str): Label used when member does not appear in one category.

    Returns:
        dict[str, Any]: Dictionary with ``categories``, ``dimensions``, ``counts``,
            and ``rows`` entries.

    Raises:
        KeyError: If ``category_order`` references unknown category.
        ValueError: If no categories are provided or one member maps to multiple
            labels within same category.
    """
    categories = (
        list(category_order)
        if category_order is not None
        else list(category_participation_dict.keys())
    )
    if not categories:
        raise ValueError("At least one category is required for alluvial data.")

    missing_categories = [
        category for category in categories if category not in category_participation_dict
    ]
    if missing_categories:
        missing_category_list = ", ".join(missing_categories)
        raise KeyError(f"Unknown categories requested: {missing_category_list}")

    member_to_categories: dict[str, dict[str, str]] = {}
    for category in categories:
        for label, member_ids in category_participation_dict[category].items():
            for member_id in member_ids:
                category_map = member_to_categories.setdefault(member_id, {})
                existing_label = category_map.get(category)
                if existing_label is not None and existing_label != label:
                    raise ValueError(
                        f"Member '{member_id}' appears in multiple labels for category "
                        f"'{category}': '{existing_label}' and '{label}'."
                    )
                category_map[category] = label

    combination_counts: Counter[tuple[str, ...]] = Counter()
    combination_members: dict[tuple[str, ...], list[str]] = {}
    for member_id, category_map in member_to_categories.items():
        combination = tuple(
            category_map.get(category, missing_label) for category in categories
        )
        combination_counts[combination] += 1
        combination_members.setdefault(combination, []).append(member_id)

    unique_combinations = list(combination_counts.keys())
    dimensions = [
        {
            "label": category,
            "values": [combination[index] for combination in unique_combinations],
        }
        for index, category in enumerate(categories)
    ]
    counts = [combination_counts[combination] for combination in unique_combinations]
    rows = [
        {
            "members": combination_members[combination],
            "count": combination_counts[combination],
            "values": {
                category: combination[index] for index, category in enumerate(categories)
            },
        }
        for combination in unique_combinations
    ]

    return {
        "categories": categories,
        "dimensions": dimensions,
        "counts": counts,
        "rows": rows,
    }


def prepare_alluvial_plot_data(
    category_participation_dict: Mapping[str, Mapping[str, Iterable[str]]],
    *,
    category_order: Sequence[str] | None = None,
    missing_label: str = "unassigned",
) -> dict[str, Any]:
    """Generated: validation needed.

    Description:
        Prepare Parcats data with category-count labels and blended path colours.

    Args:
        category_participation_dict (Mapping[str, Mapping[str, Iterable[str]]]):
            Category mapping where each category points to labels and each label
            points to member identifiers.
        category_order (Sequence[str] | None): Explicit category order for
            resulting dimensions. Defaults to insertion order from
            ``category_participation_dict``.
        missing_label (str): Label used when member does not appear in one category.

    Returns:
        dict[str, Any]: Dictionary with Parcats-ready dimensions, counts, rows,
            line colours, and label totals.
    """
    base_alluvial_data = prepare_alluvial_data(
        category_participation_dict,
        category_order=category_order,
        missing_label=missing_label,
    )
    categories: list[str] = base_alluvial_data["categories"]

    label_totals: dict[str, dict[str, int]] = {
        category: {
            label: len(list(member_ids))
            for label, member_ids in category_participation_dict[category].items()
        }
        for category in categories
    }
    label_display_map: dict[str, dict[str, str]] = {
        category: {label: f"{label}: {count}" for label, count in category_totals.items()}
        for category, category_totals in label_totals.items()
    }

    dimensions = []
    for dimension in base_alluvial_data["dimensions"]:
        category = str(dimension["label"])
        values = [
            label_display_map[category].get(str(value), str(value))
            for value in dimension["values"]
        ]
        categoryarray = [
            label_display_map[category].get(str(label), str(label))
            for label in category_participation_dict[category].keys()
        ]
        dimensions.append(
            {
                "label": category,
                "values": values,
                "categoryorder": "array",
                "categoryarray": categoryarray,
            }
        )

    colours_hex, _, _, _, _ = custom_colorblind_color_discrete_palette()
    colour_palette_iterator = cycle(colours_hex)
    category_label_colours: dict[str, dict[str, str]] = {
        category: {
            label: next(colour_palette_iterator)
            for label in category_participation_dict[category].keys()
        }
        for category in categories
    }

    line_colours = [
        blend_hex_color_sequence(
            [
                category_label_colours[category].get(
                    str(row["values"][category]),
                    "#808080",
                )
                for category in categories
            ]
        )
        for row in base_alluvial_data["rows"]
    ]

    return {
        **base_alluvial_data,
        "dimensions": dimensions,
        "line_colours": line_colours,
        "label_totals": label_totals,
    }


def create_alluvial_plot(
    alluvial_plot_data: dict[str, Any],
    plot_config: PlotConfig | None = None,
    title: str = "Alluvial Plot",
) -> go.Figure:
    if plot_config is None:
        plot_config = PlotConfig()
    fig = go.Figure(
        go.Parcats(
            dimensions=alluvial_plot_data["dimensions"],
            counts=alluvial_plot_data["counts"],
            line={"color": alluvial_plot_data["line_colours"]},
            hoveron="color",
            hoverinfo="all",
            labelfont={"color": "black", "size": 14},
            arrangement="freeform",
        )
    )
    fig.update_layout(
        title=title,
        font={"size": 12, "color": "black"},
    )

    return fig
