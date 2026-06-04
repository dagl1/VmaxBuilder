"""Performance regression test for Kcat GPR simplification.

Compares current parser/simplifier against legacy implementation that previously
lived in the `if __name__ == "__main__"` sandbox of `gpr_implementation.py`.
"""

from __future__ import annotations

import re
from pathlib import Path
from time import perf_counter

import pytest
from cobra.io import load_json_model

from VmaxBuilder.Kcat import DefaultKcatGPRImplementation

MODEL_PATH = Path(
    r"C:\git\SWaPAM\data\for_SWAMP\models\model_inhouse_v9_human\model_inhouse_v9.json"
)
ITERATIONS = 40


def _legacy_tokenize(gpr_rule: str) -> list[str]:
    token_pattern = re.compile(
        r"\(|\)|\band\b|\bor\b|[^\s()]+",
        flags=re.IGNORECASE,
    )
    return [token.strip() for token in token_pattern.findall(gpr_rule) if token.strip()]


def _legacy_parse(tokens: list[str]):
    def _helper(token_list: list[str]):
        current_nodes = []
        pending_operator = None
        while token_list:
            token = token_list.pop(0)
            if token == "(":
                current_nodes.append(_helper(token_list))
            elif token == ")":
                break
            elif token.lower() == "and":
                pending_operator = "and"
            elif token.lower() == "or":
                pending_operator = "or"
            else:
                current_nodes.append(token)

            if pending_operator == "and" and len(current_nodes) >= 2:
                right_node = current_nodes.pop()
                left_node = current_nodes.pop()
                current_nodes.append(("AND", left_node, right_node))
                pending_operator = None
            elif pending_operator == "or" and len(current_nodes) >= 2:
                right_node = current_nodes.pop()
                left_node = current_nodes.pop()
                current_nodes.append(["OR", left_node, right_node])
                pending_operator = None

        return current_nodes[0] if len(current_nodes) == 1 else current_nodes

    return _helper(tokens)


def _legacy_expand_or(tree):
    if isinstance(tree, str):
        return [[tree]]
    if isinstance(tree, tuple) and tree[0] == "AND":
        left = _legacy_expand_or(tree[1])
        right = _legacy_expand_or(tree[2])
        return [left_ifp + right_ifp for left_ifp in left for right_ifp in right]
    if isinstance(tree, list) and tree[0] == "OR":
        return _legacy_expand_or(tree[1]) + _legacy_expand_or(tree[2])
    raise ValueError(f"Unknown tree node: {tree}")


def _legacy_simplify(gpr_rule: str) -> list[str]:
    tokens = _legacy_tokenize(gpr_rule)
    parsed_tree = _legacy_parse(tokens)
    ifps = _legacy_expand_or(parsed_tree)
    return [" and ".join(ifp) for ifp in ifps]


def _legacy_build_ifps(gpr_rules: set[str]) -> dict[str, list[str]]:
    legacy_mapping: dict[str, list[str]] = {}
    for gpr_rule in sorted(gpr_rules):
        legacy_mapping[gpr_rule] = sorted(_legacy_simplify(gpr_rule))
    return legacy_mapping


def _current_build_ifps(
    implementation: DefaultKcatGPRImplementation,
    gpr_rules: set[str],
) -> dict[str, list[str]]:
    current_mapping = implementation._convert_gene_gpr_rules_to_ifp(gpr_rules)
    return {
        gpr_rule: sorted(payload["simplified_gene_ifps"])
        for gpr_rule, payload in current_mapping.items()
    }


def _normalise_for_semantic_equivalence(
    mapping: dict[str, list[str]],
) -> dict[str, list[str]]:
    return {gpr_rule: sorted(set(ifps)) for gpr_rule, ifps in mapping.items()}


@pytest.mark.slow
@pytest.mark.requires_data
def test_gpr_simplification_performance_current_is_faster_than_legacy() -> None:
    if not MODEL_PATH.exists():
        pytest.skip(f"Performance model missing: {MODEL_PATH}")

    model = load_json_model(str(MODEL_PATH))
    gpr_rules = {
        reaction.gene_reaction_rule.strip()
        for reaction in model.reactions
        if reaction.gene_reaction_rule and reaction.gene_reaction_rule.strip()
    }

    implementation = DefaultKcatGPRImplementation()
    implementation.clear_simplification_cache()

    # Warmup to reduce one-time import/interpreter effects.
    _legacy_build_ifps(gpr_rules)
    _current_build_ifps(implementation, gpr_rules)

    start_legacy = perf_counter()
    legacy_result: dict[str, list[str]] | None = None
    for _ in range(ITERATIONS):
        legacy_result = _legacy_build_ifps(gpr_rules)
    legacy_seconds = perf_counter() - start_legacy

    start_current = perf_counter()
    current_result: dict[str, list[str]] | None = None
    for _ in range(ITERATIONS):
        current_result = _current_build_ifps(implementation, gpr_rules)
    current_seconds = perf_counter() - start_current

    assert legacy_result is not None
    assert current_result is not None

    strict_equal = legacy_result == current_result
    semantic_equal = _normalise_for_semantic_equivalence(
        legacy_result
    ) == _normalise_for_semantic_equivalence(current_result)

    speedup = legacy_seconds / current_seconds
    cache_info = implementation.get_simplification_cache_info()

    print(f"Model path: {MODEL_PATH}")
    print(f"Unique GPR rules: {len(gpr_rules)}")
    print(f"Iterations per version: {ITERATIONS}")
    print(f"Legacy total seconds: {legacy_seconds:.6f}")
    print(f"Current total seconds: {current_seconds:.6f}")
    print(f"Speedup legacy/current: {speedup:.2f}x")
    print(f"Strict equality: {strict_equal}")
    print(f"Semantic equality: {semantic_equal}")
    print(f"Cache info: {cache_info}")

    assert semantic_equal, "Legacy and current results differ semantically."
    assert current_seconds < legacy_seconds, (
        "Current implementation not faster than legacy. "
        f"legacy={legacy_seconds:.6f}s current={current_seconds:.6f}s"
    )
