import re
from typing import TYPE_CHECKING, Any, Dict, Optional, Union, cast

import cobra
from cobra import Model, Reaction

from VmaxBuilder.base.configs import FullConfig

CONSERVATIVE_ENERGY_CONSUMING_REACTION_FORMULAS_DICT = {
    "ATP": [
        ["ADP", "Pi", "H+"],
        ["AMP", "PPi", "H+"],
        ["AMP", "Pi", "H+"],
        ["ADP", "PPi", "H+"],
        ["ADP", "H+", "IMP"],
        ["AMP", "H+", "IMP"],
        ["PPi", "cAMP"],
        ["ADP"],
        ["AMP"],
        ["Pi"],
        ["PPi"],
    ],
    "ADP": [
        ["AMP", "Pi", "H+"],
        ["AMP", "PPi", "H+"],
        ["AMP", "H+", "IMP"],
        ["AMP"],
        ["Pi"],
        ["PPi"],
    ],
    "GTP": [
        ["GDP", "Pi", "H+"],
        ["GMP", "PPi", "H+"],
        ["GMP", "Pi", "H+"],
        ["GDP", "PPi", "H+"],
        ["GDP", "H+", "IMP"],
        ["GMP", "H+", "IMP"],
        ["PPi", "cGMP"],
        ["GDP"],
        ["GMP"],
        ["Pi"],
        ["PPi"],
    ],
    "GDP": [
        ["GMP", "Pi", "H+"],
        ["GMP", "PPi", "H+"],
        ["GMP", "H+", "IMP"],
        ["GMP"],
        ["Pi"],
        ["PPi"],
    ],
    "UTP": [
        ["UDP", "Pi", "H+"],
        ["UMP", "PPi", "H+"],
        ["UMP", "Pi", "H+"],
        ["UDP", "PPi", "H+"],
        ["UDP", "H+", "IMP"],
        ["UMP", "H+", "IMP"],
        ["PPi", "cUMP"],
        ["UDP"],
        ["UMP"],
        ["Pi"],
        ["PPi"],
    ],
    "UDP": [
        ["UMP", "Pi", "H+"],
        ["UMP", "PPi", "H+"],
        ["UMP", "H+", "IMP"],
        ["UMP"],
        ["Pi"],
        ["PPi"],
    ],
    "CTP": [
        ["CDP", "Pi", "H+"],
        ["CMP", "PPi", "H+"],
        ["CMP", "Pi", "H+"],
        ["CDP", "PPi", "H+"],
        ["CDP", "H+", "IMP"],
        ["CMP", "H+", "IMP"],
        ["PPi", "cCMP"],
        ["CDP"],
        ["CMP"],
        ["Pi"],
        ["PPi"],
    ],
    "CDP": [
        ["CMP", "Pi", "H+"],
        ["CMP", "PPi", "H+"],
        ["CMP", "H+", "IMP"],
        ["CMP"],
        ["Pi"],
        ["PPi"],
    ],
    "AMP": [
        ["Adenosine", "Pi"],
        ["Adenosine", "H+"],
        ["Adenosine", "PPi"],
        ["Pi"],
        ["H+", "IMP"],
        ["PPi"],
    ],
    "PPi": [["Pi"], ["H+", "IMP"]],
    "Acetyl-CoA": [["CoA", "Acetate"]],  # Acetyl-CoA hydrolysis
    "Succinyl-CoA": [["CoA", "Succinate"]],  # Succinyl-CoA hydrolysis
    "UDP-Glucose": [["UDP", "Glucose"]],  # UDP-glucose as a sugar donor
    "PAP": [["AMP", "Pi"]],  # PAP → AMP + Pi
    "PAPS": [["PAP", "SO4"]],
    "ITP": [
        ["IMP", "Pi", "H+"],
        ["Inosine", "Pi", "H+"],
        ["IMP", "PPi", "H+"],
        ["Inosine", "PPi", "H+"],
        ["IMP", "H+"],
        ["Inosine", "H+"],
        ["IMP", "Pi"],
        ["Inosine", "Pi"],
        ["IMP", "PPi"],
        ["Inosine", "PPi"],
        ["IMP"],
        ["Inosine"],
        ["Pi"],
        ["PPi"],
    ],
    "IDP": [
        ["IMP", "Pi", "H+"],
        ["Inosine", "Pi", "H+"],
        ["IMP", "PPi", "H+"],
        ["Inosine", "PPi", "H+"],
        ["IMP", "H+"],
        ["Inosine", "H+"],
        ["IMP", "Pi"],
        ["Inosine", "Pi"],
        ["IMP", "PPi"],
        ["Inosine", "PPi"],
        ["IMP"],
        ["Inosine"],
        ["Pi"],
        ["PPi"],
    ],
}


def _metabolite_has_same_identifiers(met1: Any, met2: Any) -> bool:
    """Generated: validation needed.

    Description:
        Compare metabolite identifiers after stripping compartment suffixes.

    Args:
        met1 (Any): First metabolite-like object.
        met2 (Any): Second metabolite-like object.

    Returns:
        bool: True when identifiers match after compartment removal.
    """
    met_1_id = met1.id
    met_1_compartment = met1.compartment
    if met_1_id.endswith(f"[{met_1_compartment}]"):
        met_1_id = met_1_id[: -len(f"[{met_1_compartment}]")]
    elif met_1_id.endswith(f"_{met_1_compartment}"):
        met_1_id = met_1_id[: -len(f"_{met_1_compartment}")]
    elif met_1_id.endswith(met_1_compartment):
        met_1_id = met_1_id[: -len(met_1_compartment)]
    met_2_id = met2.id
    met_2_compartment = met2.compartment
    if met_1_id.endswith(f"[{met_1_compartment}]"):
        met_1_id = met_1_id[: -len(f"[{met_1_compartment}]")]
    elif met_2_id.endswith(f"_{met_2_compartment}"):
        met_2_id = met_2_id[: -len(f"_{met_2_compartment}")]
    elif met_2_id.endswith(met_2_compartment):
        met_2_id = met_2_id[: -len(met_2_compartment)]

    return met_1_id == met_2_id


def _metabolite_has_same_names(met1: Any, met2: Any) -> bool:
    """Generated: validation needed.

    Description:
        Compare metabolite names after trimming whitespace.

    Args:
        met1 (Any): First metabolite-like object.
        met2 (Any): Second metabolite-like object.

    Returns:
        bool: True when names match exactly after strip.
    """
    met_1_name = met1.name.strip()
    met_2_name = met2.name.strip()
    return met_1_name == met_2_name


def _metabolite_has_same_formula(
    met1: Any,
    met2: Any,
    ignore_h_plus: bool = False,
) -> bool:
    """Generated: validation needed.

    Description:
        Compare metabolite formulas, optionally ignoring hydrogen fragments.

    Args:
        met1 (Any): First metabolite-like object.
        met2 (Any): Second metabolite-like object.
        ignore_h_plus (bool): When True, compare formulas after removing hydrogen fragments.

    Returns:
        bool: True when formulas match under selected comparison mode.
    """
    met_1_formula = met1.formula.strip() if met1.formula is not None else None
    met_2_formula = met2.formula.strip() if met2.formula is not None else None
    if ignore_h_plus:
        if met_1_formula is None or met_2_formula is None:
            return False
        # remove all H+ and h+ from the formula before comparing
        met_1_formula = (
            met_1_formula.replace("H+", "")
            .replace("h+", "")
            .replace("H", "")
            .replace("h", "")
        )
        met_2_formula = (
            met_2_formula.replace("H+", "")
            .replace("h+", "")
            .replace("H", "")
            .replace("h", "")
        )
        return met_1_formula == met_2_formula
    return met_1_formula == met_2_formula


def _metabolite_has_same_charge(
    met1: Any,
    met2: Any,
    ignore_h_plus: bool = False,
) -> bool:
    """Generated: validation needed.

    Description:
        Compare metabolite charges, optionally adjusting for hydrogen fragments.

    Args:
        met1 (Any): First metabolite-like object.
        met2 (Any): Second metabolite-like object.
        ignore_h_plus (bool): When True, subtract hydrogen fragments from charge.

    Returns:
        bool: True when charges match under selected comparison mode.
    """
    if ignore_h_plus:
        if met1.charge is None or met2.charge is None:
            return False
        # count the number of H+ and h+ in the formula and adjust the charge accordingly
        h_plus_count1 = met1.formula.lower().count("h+") + met1.formula.lower().count("h")
        h_plus_count2 = met2.formula.lower().count("h+") + met2.formula.lower().count("h")
        adjusted_charge1 = met1.charge - h_plus_count1
        adjusted_charge2 = met2.charge - h_plus_count2
        adjusted_charge1 = int(adjusted_charge1)
        adjusted_charge2 = int(adjusted_charge2)
        return adjusted_charge1 == adjusted_charge2
    met_1_charge = int(met1.charge) if met1.charge is not None else None
    met_2_charge = int(met2.charge) if met2.charge is not None else None
    return met_1_charge == met_2_charge


def match_metabolite_with_model_metabolites(
    metabolite_without_compartment: str,
    compartment: str,
    model_metabolites: list[cobra.Metabolite],
) -> cobra.Metabolite | None:
    for model_metabolite in model_metabolites:
        model_metabolite_id = model_metabolite.id
        model_metabolite_compartment = model_metabolite.compartment
        if model_metabolite_id.endswith(f"[{model_metabolite_compartment}]"):
            model_metabolite_id = model_metabolite_id[
                : -len(f"[{model_metabolite_compartment}]")
            ]
        elif model_metabolite_id.endswith(f"_{model_metabolite_compartment}"):
            model_metabolite_id = model_metabolite_id[
                : -len(f"_{model_metabolite_compartment}")
            ]
        elif model_metabolite_id.endswith(model_metabolite_compartment):  # ty:ignore
            # ty:ignore
            model_metabolite_id = model_metabolite_id[: -len(model_metabolite_compartment)]
        if (
            metabolite_without_compartment == model_metabolite_id
            and compartment == model_metabolite_compartment
        ):
            return model_metabolite


def extract_compartment(old_id: Any) -> str | None:
    """Generated: validation needed.

    Description:
        Extract compartment suffix from metabolite identifier.

    Args:
        old_id (Any): Identifier to inspect. Non-string values return empty string.

    Returns:
        str: Extracted compartment or empty string when absent.
    """
    if not isinstance(old_id, str):
        return ""
    # underscore form: "MAM20065_c" or "MAM20065_cyt"
    m = re.search(r"_(?P<comp>[A-Za-z]+)$", old_id)
    if m:
        return m.group("comp")
    # trailing letters after digits: "MAM20065n" or "MAM20065cg"
    m = re.search(r"^[A-Za-z]*\d+(?P<comp>[A-Za-z]+)$", old_id)
    if m:
        return m.group("comp")
    # [comp] form: "MAM20065[c]" or "MAM20065[cyt]"
    m = re.search(r"\[(?P<comp>[A-Za-z]+)]$", old_id)
    if m:
        return m.group("comp")
    return None


def remove_compartment(old_id: Any) -> Any:
    """Generated: validation needed.

    Description:
        Remove compartment suffix from metabolite identifier.

    Args:
        old_id (Any): Identifier to normalise. Non-string values are returned unchanged.

    Returns:
        Any: Identifier without compartment suffix when pattern matches.
    """
    if not isinstance(old_id, str):
        return old_id
    # underscore form: "MAM20065_c" or "MAM20065_cyt"
    new_id = re.sub(
        r"^(MAM\d+)(?:_[A-Za-z]+|[A-Za-z]+)$",
        r"\1",
        old_id,
    )
    # [comp] form: "MAM20065[c]" or "MAM20065[cyt]"
    new_id = re.sub(r"^(MAM\d+)\[([A-Za-z]+)]$", r"\1", new_id)
    return new_id


def convert_camel_case_to_snake_case(name: str) -> str:
    """Generated: validation needed.

    Description:
        Convert camelCase string to snake_case.

    Args:
        name (str): Input name.

    Returns:
        str: Snake case version of name.
    """
    if not name:
        return name
    result = [name[0].lower()]
    for char in name[1:]:
        if char.isupper():
            result.append("_")
            result.append(char.lower())
        else:
            result.append(char)
    return "".join(result)


def convert_model_to_cobra_model(
    model: Union["Model", Dict[str, Any]], make_copy: Optional[bool] = False
) -> "Model":
    """Generated: validation needed.

    Description:
        Convert a model-like object to a COBRApy Model.  Not yet implemented.

    Args:
        model (Model | Dict[str, Any]): Source model or raw dictionary.
        make_copy (Optional[bool]): Reserved for future copy semantics.

    Raises:
        NotImplementedError: Always raised; conversion not yet implemented.
    """
    raise NotImplementedError(
        "This function is not implemented in the VmaxBuilder package. "
        "Please use the appropriate method from the VmaxBuilder package to convert models."
    )  # todo


def is_effectively_integer(value: Any) -> bool:
    """Generated: validation needed.

    Description:
        Check whether value can be represented as integer without remainder.

    Args:
        value (Any): Candidate numeric value.

    Returns:
        bool: True when float conversion succeeds and is integer-like.
    """
    try:
        return float(value).is_integer()
    except (ValueError, TypeError):
        return False


def check_if_string_or_integer(column: Any) -> bool:
    """Generated: validation needed.

    Description:
        Check whether column contains enough string or integer-like values.

    Args:
        column (Any): Column-like object supporting astype and string contains.

    Returns:
        bool: True when string or integer counts meet threshold.
    """
    string_count = column.astype(str).str.contains("[a-zA-Z]").sum()
    integer_count = column.astype(str).str.contains("[0-9]").sum()
    return string_count >= 2 or integer_count >= 2


def _deduplicate_preserve_order(values: list[str]) -> list[str]:
    """Generated: validation needed.

    Description:
        Deduplicate strings while preserving first-seen order.

    Args:
        values (list[str]): Input string list.

    Returns:
        list[str]: Ordered unique string list.
    """
    return list(dict.fromkeys(values))


def _validate_cobra_model_or_reactions(
    cobra_model: Model | None = None, reactions: list[Reaction] | None = None
) -> list[Reaction]:
    if cobra_model is None and reactions is None:
        raise ValueError("Either cobra_model or reactions must be provided.")
    elif cobra_model is not None:
        return cobra_model.reactions
    elif reactions is not None:
        return reactions
    else:
        raise ValueError("Unexpected state: both cobra_model and reactions are None.")


def find_energy_carrier_reactions(
    cobra_model: Model | None = None, reactions: list[Reaction] | None = None
) -> tuple[list[Reaction], list[Reaction], list[Reaction], list[Reaction]]:
    reactions = _validate_cobra_model_or_reactions(cobra_model, reactions)

    energy_carrier_containing_reactions = []
    found_with_conservative = []

    for reaction in reactions:
        reactants = reaction.reactants
        products = reaction.products
        converted_reactants = [met.name for met in reactants]
        converted_products = [met.name for met in products]
        found_in_conservative = False
        for key in CONSERVATIVE_ENERGY_CONSUMING_REACTION_FORMULAS_DICT.keys():
            if found_in_conservative:
                break
            if key in converted_reactants:
                for formula in CONSERVATIVE_ENERGY_CONSUMING_REACTION_FORMULAS_DICT[key]:
                    if all([met in converted_products for met in formula]):
                        found_with_conservative.append(reaction)
                        found_in_conservative = True
                        break
            elif key in converted_products:
                for formula in CONSERVATIVE_ENERGY_CONSUMING_REACTION_FORMULAS_DICT[key]:
                    if all([met in converted_reactants for met in formula]):
                        found_with_conservative.append(reaction)
                        found_in_conservative = True
                        break

    not_found_but_containing_energy_carriers = [
        reaction for reaction in energy_carrier_containing_reactions
    ]
    found_only_in_conservative = [reaction for reaction in found_with_conservative]

    return (
        found_with_conservative,
        found_only_in_conservative,
        not_found_but_containing_energy_carriers,
        energy_carrier_containing_reactions,
    )


def _get_reaction_compartments(reaction: Reaction) -> set[str]:
    """Generated: validation needed.

    Description:
        Collect distinct compartments touched by reaction metabolites.

    Args:
        reaction (Reaction): Cobra reaction to inspect.

    Returns:
        set[str]: Compartments present in reaction.
    """
    return {
        metabolite.compartment
        for metabolite in reaction.metabolites
        if metabolite.compartment is not None
    }


def get_transport_reactions(
    reactions: list[Reaction],
) -> tuple[list[Reaction], list[Reaction]]:
    # active vs non active transport reactions
    # active is based on energy carrier reactions
    active_transport_reactions = []
    passive_transport_reactions = []
    (
        energy_carrier_containing_reactions,
        _,
        _,
        _,
    ) = find_energy_carrier_reactions(reactions=reactions)

    energy_carrier_containing_reactions_ids = {
        reaction.id for reaction in energy_carrier_containing_reactions
    }

    for reaction in reactions:
        _compartments = _get_reaction_compartments(reaction)
        if len(reaction.compartments) > 1:
            if reaction.id not in energy_carrier_containing_reactions_ids:
                passive_transport_reactions.append(reaction)
                continue
            elif reaction.id in energy_carrier_containing_reactions_ids:
                active_transport_reactions.append(reaction)

    return (active_transport_reactions, passive_transport_reactions)


def get_transport_reaction_gene_ids(
    cobra_model: Model,
    expression_gene_ids: set[str] | None = None,
) -> tuple[list[str], list[str], list[str]]:
    reactions = cobra_model.reactions

    results_energy_carriers = find_energy_carrier_reactions(cobra_model)
    reactions_containing_energy_carriers = results_energy_carriers[0]
    non_energy_carrier_containing_reaction = [
        rxn
        for rxn in cobra_model.reactions
        if rxn not in reactions_containing_energy_carriers
    ]

    transport_reactions = []
    passive_transport_reactions = []
    active_transport_reactions = []

    transport_reaction_gene_ids = set()
    passive_transport_reaction_gene_ids = set()
    active_transport_reaction_gene_ids = set()
    for reaction in reactions:
        if len(reaction.compartments) > 1 and reaction.gene_reaction_rule:
            transport_reactions.append(reaction)
            transport_reaction_gene_ids.update(str(gene.id) for gene in reaction.genes)
            if reaction in non_energy_carrier_containing_reaction:
                passive_transport_reactions.append(reaction)
                passive_transport_reaction_gene_ids.update(
                    str(gene.id) for gene in reaction.genes
                )
            elif reaction in reactions_containing_energy_carriers:
                active_transport_reactions.append(reaction)
                active_transport_reaction_gene_ids.update(
                    str(gene.id) for gene in reaction.genes
                )

    _non_transport_reactions = [
        reaction for reaction in reactions if reaction not in transport_reactions
    ]
    non_transport_reaction_gene_ids = set(
        str(gene.id) for gene in cobra_model.genes if gene not in transport_reaction_gene_ids
    )

    if expression_gene_ids is not None:
        active_transport_reaction_gene_ids = [
            gene_id
            for gene_id in active_transport_reaction_gene_ids
            if gene_id in expression_gene_ids
        ]
        passive_transport_reaction_gene_ids = [
            gene_id
            for gene_id in passive_transport_reaction_gene_ids
            if gene_id in expression_gene_ids
        ]
        non_transport_reaction_gene_ids = [
            gene_id
            for gene_id in non_transport_reaction_gene_ids
            if gene_id in expression_gene_ids
        ]

    active_transport_reaction_gene_ids = _deduplicate_preserve_order(
        list(active_transport_reaction_gene_ids)
    )
    passive_transport_reaction_gene_ids = _deduplicate_preserve_order(
        list(passive_transport_reaction_gene_ids)
    )
    non_transport_reaction_gene_ids = _deduplicate_preserve_order(
        list(non_transport_reaction_gene_ids)
    )

    return (
        active_transport_reaction_gene_ids,
        passive_transport_reaction_gene_ids,
        non_transport_reaction_gene_ids,
    )


def compare_dicts(
    dict1: Dict[str, Any],
    dict2: Dict[str, Any],
) -> None:
    """Generated: validation needed.

    Description:
        Print a human-readable diff of two dictionaries to stdout, listing keys
        unique to each dict and value differences for shared keys.

    Args:
        dict1 (Dict[str, Any]): First dictionary.
        dict2 (Dict[str, Any]): Second dictionary.
    """
    if dict1 == dict2:
        print("Dictionaries are equal.")
        return

    print("Dictionaries differ:")

    keys1 = set(dict1.keys())
    keys2 = set(dict2.keys())

    only_in_1 = keys1 - keys2
    only_in_2 = keys2 - keys1
    common_keys = keys1 & keys2

    if only_in_1:
        print("  Keys only in dict1:", only_in_1)
    if only_in_2:
        print("  Keys only in dict2:", only_in_2)

    for key in common_keys:
        if dict1[key] != dict2[key]:
            print(f"  Different value for key '{key}':")
            print(f"    dict1: {dict1[key]}")
            print(f"    dict2: {dict2[key]}")


def create_task_specific_model_for_diagnostics(  # noqa: C901
    irreversible_cobra_model: "Model",
    task_information: Dict[str, Any],
    unbounded_lower_bound_value: float | int = 1,
    unbounded_upper_bound_value: float | int = 1000,
    make_copy: bool = False,
):
    """Generated: validation needed.

    Description:
        Add temporary exchange reactions for task-specific diagnostics.

    Args:
        irreversible_cobra_model (Model): Model to modify.
        task_information (Dict[str, Any]): Task metadata with input/output metabolites.
        unbounded_lower_bound_value (float | int): Lower bound fallback for unbounded inputs.
        unbounded_upper_bound_value (float | int): Upper bound fallback for unbounded bounds.
        make_copy (bool): Copy model before mutation when True.

    Returns:
        tuple[Model, list[Any]]: Modified model and reactions added to it.
    """
    if make_copy:
        irreversible_cobra_model = irreversible_cobra_model.copy()

    reactions_in_both_input_and_output = set(
        task_information["input_metabolites"]
    ).intersection(set(task_information["output_metabolites"]))
    amount_of_input_reactions = len(task_information["input_metabolites"])
    amount_of_output_reactions = len(task_information["output_metabolites"])
    added_reactions = []
    for idx in range(amount_of_input_reactions):
        if task_information["input_metabolites"][idx] in reactions_in_both_input_and_output:
            continue
        metabolite = task_information["input_metabolites"][idx]
        lower_bound = task_information["input_metabolite_lower_bounds"][idx]
        upper_bound = task_information["input_metabolite_upper_bounds"][idx]
        if lower_bound == "unbounded":
            lower_bound = unbounded_lower_bound_value
        if upper_bound == "unbounded":
            upper_bound = unbounded_upper_bound_value

        new_reaction = Reaction("temporary_exchange_metabolite")
        new_reaction.name = f"temporary_exchange_{metabolite}"
        new_reaction.id = f"temporary_exchange_{metabolite}"
        new_reaction.subsystem = "temporary_exchange"
        cast(Any, new_reaction).EC_number = ""
        new_reaction.lower_bound = lower_bound
        new_reaction.upper_bound = upper_bound
        metabolite_object = irreversible_cobra_model.metabolites.get_by_id(metabolite)
        new_reaction.add_metabolites({metabolite_object: 1})
        irreversible_cobra_model.add_reactions([new_reaction])
        added_reactions.append(new_reaction)
    for idx in range(amount_of_output_reactions):
        if task_information["output_metabolites"][idx] in reactions_in_both_input_and_output:
            continue
        metabolite = task_information["output_metabolites"][idx]
        lower_bound = task_information["output_metabolite_lower_bounds"][idx]
        upper_bound = task_information["output_metabolite_upper_bounds"][idx]
        if lower_bound == "unbounded":
            lower_bound = unbounded_lower_bound_value
        if upper_bound == "unbounded":
            upper_bound = unbounded_upper_bound_value
        # add exchange reaction for output metabolite
        new_reaction = Reaction(f"temporary_exchange_{metabolite}")
        new_reaction.name = f"temporary_exchange_{metabolite}"
        new_reaction.id = f"temporary_exchange_{metabolite}"
        new_reaction.subsystem = "temporary_exchange"
        cast(Any, new_reaction).EC_number = ""
        new_reaction.lower_bound = lower_bound
        new_reaction.upper_bound = upper_bound
        metabolite_object = irreversible_cobra_model.metabolites.get_by_id(metabolite)
        new_reaction.add_metabolites({metabolite_object: -1})
        irreversible_cobra_model.add_reactions([new_reaction])
        added_reactions.append(new_reaction)
    for metabolite in reactions_in_both_input_and_output:
        input_upper_bound = task_information["input_metabolite_upper_bounds"][
            task_information["input_metabolites"].index(metabolite)
        ]
        output_upper_bound = task_information["output_metabolite_upper_bounds"][
            task_information["output_metabolites"].index(metabolite)
        ]
        if input_upper_bound == "unbounded":
            input_upper_bound = unbounded_upper_bound_value
        if output_upper_bound == "unbounded":
            output_upper_bound = unbounded_upper_bound_value

        new_reaction = Reaction(f"temporary_exchange_{metabolite}_f")
        new_reaction.name = f"temporary_exchange_{metabolite}_f"
        new_reaction.id = f"temporary_exchange_{metabolite}_f"
        new_reaction.subsystem = "temporary_exchange"
        new_reaction.lower_bound = 0
        cast(Any, new_reaction).EC_number = ""
        new_reaction.upper_bound = input_upper_bound
        metabolite_object = irreversible_cobra_model.metabolites.get_by_id(metabolite)
        new_reaction.add_metabolites({metabolite_object: 1})
        irreversible_cobra_model.add_reactions([new_reaction])
        added_reactions.append(new_reaction)

        new_reaction = Reaction(f"temporary_exchange_{metabolite}_r")
        new_reaction.name = f"temporary_exchange_{metabolite}_r"
        new_reaction.id = f"temporary_exchange_{metabolite}_r"
        new_reaction.subsystem = "temporary_exchange"
        new_reaction.lower_bound = 0
        cast(Any, new_reaction).EC_number = ""
        new_reaction.upper_bound = output_upper_bound
        metabolite_object = irreversible_cobra_model.metabolites.get_by_id(metabolite)
        new_reaction.add_metabolites({metabolite_object: -1})
        irreversible_cobra_model.add_reactions([new_reaction])
        added_reactions.append(new_reaction)

    return irreversible_cobra_model, added_reactions


if __name__ == "__main__":
    # Example usage of the utility functions
    print("This module provides utility functions for VmaxBuilder.")

    met_id_1 = "MAM20065_c"
    met_id_2 = "MAM20065[cyt]"
    met_id_3 = "MAM20065cg"
    met_id_4 = "MAM20065"

    # Test extract_compartment
    print(f"Compartment of {met_id_1}: {extract_compartment(met_id_1)}")
    print(f"Compartment of {met_id_2}: {extract_compartment(met_id_2)}")
    print(f"Compartment of {met_id_3}: {extract_compartment(met_id_3)}")
    print(f"Compartment of {met_id_4}: {extract_compartment(met_id_4)}")

    # Test remove_compartment
    print(f"ID without compartment of {met_id_1}: {remove_compartment(met_id_1)}")
    print(f"ID without compartment of {met_id_2}: {remove_compartment(met_id_2)}")
    print(f"ID without compartment of {met_id_3}: {remove_compartment(met_id_3)}")
    print(f"ID without compartment of {met_id_4}: {remove_compartment(met_id_4)}")
