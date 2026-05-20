"""Cobrapy I/O function overrides and enhancements.

This module patches cobra I/O functions to fix bugs and add missing
features for handling model serialisation (MATLAB, JSON formats).

**Key enhancements:**
- Load/save MATLAB models with better error handling
- Handle NaN and Na values during JSON serialisation
- Support rxnECNumber field from MATLAB structs
- Handle geneShortNames field as fallback
- Load subsystems correctly from MATLAB arrays

**Changes made:**
- 2025-01-22: Initial wrapper around load_mat; EC number support
- 2025-02-11: Fixed subsystem loading from MATLAB arrays
- 2025-06-20: Consolidated and documented all I/O fixes

Author: Jelle Bonthuis (MaCSBio)
"""

import json
from collections import OrderedDict
from logging import getLogger
from pathlib import Path

# imports
from typing import IO, Any, Dict, Optional, Union, cast

import numpy as np
from cobra import Gene, Metabolite, Model, Reaction
from cobra.core.object import Object
from cobra.io.dict import (
    _OPTIONAL_MODEL_ATTRIBUTES,
    _ORDERED_OPTIONAL_MODEL_KEYS,
    _REQUIRED_REACTION_ATTRIBUTES,
    _fix_type,
    _gene_to_dict,
    _metabolite_from_dict,
    _metabolite_to_dict,
    _reaction_from_dict,
    _update_optional,
    attrgetter,
    gene_from_dict,
    itemgetter,
)
from cobra.io.json import JSON_SPEC
from cobra.io.mat import (
    DICT_GENE,
    DICT_MET,
    DICT_MET_NOTES,
    DICT_REACTION,
    DICT_REACTION_NOTES,
    Group,
    _cell_to_float_list,
    _cell_to_str_list,
    _get_id_compartment,
    mat_parse_annotations,
    mat_parse_notes,
    set_objective,
)

try:
    from scipy.io.matlab import loadmat
    from scipy.sparse import csc_matrix

    SCIPY_INSTALLED = True
except ImportError:
    SCIPY_INSTALLED = False
logger = getLogger(__name__)

#### Jelle Bonthuis 2025-01-22: Added rxnECNumber to the list of valid fields
_ORDERED_OPTIONAL_REACTION_KEYS = [
    "objective_coefficient",
    "subsystem",
    "notes",
    "annotation",
    # "EC_number",
]
_OPTIONAL_REACTION_ATTRIBUTES = {
    "objective_coefficient": 0,
    "subsystem": "",
    "notes": {},
    "annotation": {},
    # "EC_number": "",
}

_REACTION_FIELDS_TO_CHECK = [
    "id",
    "name",
    "subsystem",
    "gene_reaction_rule",
    "lower_bound",
    "upper_bound",
    "gene_reaction_rule",
]

_META_FIELDS_TO_CHECK = [
    "id",
    "name",
    "formula",
    "charge",
    "compartment",
    "annotation",
    "notes",
    "inchis",
]

_GENE_FIELDS_TO_CHECK = ["id", "name", "annotation", "notes"]


def load_matlab_model(  # noqa: C901
    infile_path: Union[str, Path, IO],
    variable_name: Optional[str] = None,
    inf: float = np.inf,
) -> Model:
    """Load cobrapy Model from MATLAB .mat file with error handling.

    Wraps scipy.io.loadmat with meaningful error messages for common issues
    (e.g., non-alphanumeric characters in identifiers). Delegates struct
    conversion to from_mat_struct() for metabolite, reaction, gene parsing.
    Handles field name remapping (old → new cobratoolbox field names).

    Args:
        infile_path (str | Path | IO): File path or file handle to .mat file.
        variable_name (str | None, optional): Variable name in .mat file.
            If None, auto-selects first valid model structure. Defaults to None.
        inf (float, optional): Bound value for infinite bounds. Defaults to np.inf.

    Returns:
        cobra.Model: Loaded model with metabolites, reactions, genes,
            bounds, and EC numbers (if rxnECNumber present).

    Raises:
        ImportError: scipy not installed.
        RuntimeError: .mat file contains non-alphanumeric identifiers or buffer errors.
        IOError: No valid model found or file read failed.

    Requires:
        scipy.io.matlab.loadmat, scipy.sparse.csc_matrix

    Modifies:
        None (pure function).

    Example:
        >>> from VmaxBuilder.cobrapy_overwrites import cobrapy_io
        >>> model = cobrapy_io.load_matlab_model('data/model.mat')
        >>> print(
            f"Reactions: {len(model.reactions)},
            f"Metabolites: {len(model.metabolites)}"
        )  # doctest: +SKIP
        Reactions: 2500, Metabolites: 1500
    """
    if not SCIPY_INSTALLED:
        raise ImportError("load_matlab_model() requires scipy.")

    ### Jelle Bonthuis 2025-01-22: Try/except added
    try:
        if isinstance(infile_path, str):
            data = loadmat(infile_path)
        elif isinstance(infile_path, Path):
            data = loadmat(str(infile_path))
        else:
            data = loadmat(infile_path)  # ty: ignore[invalid-argument-type]  # noqa W9018
    except TypeError as e:
        if "buffer is too small" in str(e):
            raise RuntimeError(
                f"Error loading .mat file: {e}"
                f"This can be due to problems with non-alpha "
                f"numeric characters (e.g. greek symbols) in the model."
            ) from e
        else:
            raise IOError(f"Error loading .mat file: {e}") from e

    possible_names = []
    if variable_name is None:
        # skip meta variables
        meta_vars = {"__globals__", "__header__", "__version__"}
        possible_names = sorted(i for i in data if i not in meta_vars)
        if len(possible_names) == 1:
            variable_name = possible_names[0]
    elif variable_name is not None:
        return from_mat_struct(data[variable_name], model_id=variable_name, inf=inf)

    for possible_name in possible_names:
        # return from_mat_struct(data[possible_name], model_id=possible_name, inf=inf)
        try:
            return from_mat_struct(data[possible_name], model_id=possible_name, inf=inf)
        except ValueError:
            #### added by Jelle Bonthuis 2025-01-22: Added warning for error
            logger.warning(f"Error loading model {possible_name}")
            pass  # SHOULD NOT HAVE A RAISE FOR THIS IS ONLY OPTIONAL
            # TODO: use custom cobrapy_fork exception to handle exception
    # If code here is executed, then no model was found.
    raise IOError(f"No cobrapy_fork model found at {infile_path}.")


def from_mat_struct(  # noqa: C901
    mat_struct: np.ndarray,
    model_id: Optional[str] = None,
    inf: float = np.inf,
) -> Model:
    """Convert MATLAB struct to cobra Model object.

    Extracts metabolites, reactions, genes, bounds, EC numbers, compartments
    from MATLAB struct (scipy.io.loadmat output). Handles field name variations
    (old: confidenceScores → new: rxnConfidenceScores, etc.).

    Args:
        mat_struct (np.ndarray): MATLAB struct with fields: rxns, mets, S,
            lb, ub (required). Optional: metComps, comps, compNames, genenames,
            subSystems, rxnECNumber, notes, annotation, etc.
        model_id (str | None, optional): Model ID to assign. If None, extracted
            from 'description' field or defaults to 'imported_model'. Defaults to None.
        inf (float, optional): Value for infinite bounds. Defaults to np.inf.

    Returns:
        cobra.Model: Complete model with all components added, ready for analysis.

    Raises:
        ValueError: mat_struct missing required fields or invalid subsystem data.

    Requires:
        MATLAB struct with required: rxns, mets, S, lb, ub

    Modifies:
        Reads from mat_struct, creates new Model (no side effects on input).

    Example:
        >>> from scipy.io import loadmat
        >>> from VmaxBuilder.cobrapy_overwrites import cobrapy_io
        >>> data = loadmat('model.mat')
        >>> model = cobrapy_io.from_mat_struct(data['model'])
        >>> model.id  # doctest: +SKIP
        'RECON3D'
    """
    m = mat_struct
    #### Jelle Bonthuis 2025-01-22: Added rxnECNumber to the list of valid fields
    ##### as well as eccodes
    if m.dtype.names is None or {"rxns", "mets", "S", "lb", "ub"} > set(m.dtype.names):
        raise ValueError("Invalid MATLAB struct.")

    # Narrow dtype.names: guaranteed non-None after guard above.
    dtype_names = m.dtype.names

    old_cobratoolbox_fields = [
        "confidenceScores",
        "metCharge",
        "ecNumbers",
        "eccodes",
        "KEGGID",
        "metSmile",
        "metHMDB",
    ]
    new_cobratoolbox_fields = [
        "rxnConfidenceScores",
        "metCharges",
        "rxnECNumber",
        "rxnECNumber",
        "metKEGGID",
        "metSmiles",
        "metHMDBID",
    ]
    for old_field, new_field in zip(
        old_cobratoolbox_fields, new_cobratoolbox_fields, strict=False
    ):
        if old_field in dtype_names and new_field not in dtype_names:
            logger.warning(
                f"This model seems to have {old_field} instead of {new_field} field. "
                f"Will use {old_field} for what {new_field} represents."
            )
            new_names = list(dtype_names)
            new_names[new_names.index(old_field)] = new_field
            m.dtype.names = tuple(new_names)
            dtype_names = tuple(new_names)  # keep narrowed local in sync

    model = Model()
    if model_id is not None:
        model.id = model_id
    elif "description" in dtype_names:
        description = m["description"][0, 0][0]
        if not isinstance(description, str) and len(description) > 1:
            model.id = description[0]
            logger.warning("Several IDs detected, only using the first.")
        else:
            model.id = description
    else:
        model.id = "imported_model"
    if "modelName" in dtype_names and np.size(m["modelName"][0, 0]):
        model.name = m["modelName"][0, 0][0]

    met_ids = _cell_to_str_list(m["mets"][0, 0])
    if {"metComps", "comps", "compNames"}.issubset(dtype_names):
        met_comp_index = [x[0] - 1 for x in m["metComps"][0][0]]
        comps = _cell_to_str_list(m["comps"][0, 0])
        comp_names = _cell_to_str_list(m["compNames"][0][0])
        met_comps = [comps[i] for i in met_comp_index]
        met_comp_names = [comp_names[i] for i in met_comp_index]
    else:
        logger.warning(
            f"No defined compartments in model {model.id}. "
            f"Compartments will be deduced heuristically "
            f"using regular expressions."
        )
        met_comps = [_get_id_compartment(x) for x in met_ids]
        met_comp_names = met_comps
        if None in met_comps or "" in met_comps:
            raise ValueError("Some compartments were empty. Check the model!")
        logger.warning(
            f"Using regular expression found the following compartments:"
            f"{', '.join(sorted(set(met_comps)))}"
        )
    if None in met_comps or "" in met_comps:
        raise ValueError("Some compartments were empty. Check the model!")
    model.compartments = dict(zip(met_comps, met_comp_names, strict=False))
    met_names, met_formulas, met_charges, met_inchis = None, None, None, None
    try:
        met_names = _cell_to_str_list(m["metNames"][0, 0], "")
    except (IndexError, ValueError):
        # TODO: use custom cobrapy_fork exception to handle exception
        pass
    try:
        met_formulas = _cell_to_str_list(m["metFormulas"][0, 0])
    except (IndexError, ValueError):
        # TODO: use custom cobrapy_fork exception to handle exception
        pass
    try:
        met_charges = _cell_to_float_list(m["metCharges"][0, 0])
    except (IndexError, ValueError):
        # TODO: use custom cobrapy_fork exception to handle exception
        pass
    try:
        met_inchis = _cell_to_str_list(m["inchis"][0, 0])
    except Exception:
        pass

    new_metabolites = []
    for i in range(len(met_ids)):
        new_metabolite = Metabolite(met_ids[i], compartment=met_comps[i])
        if met_names:
            new_metabolite.name = met_names[i]
        if met_charges:
            new_metabolite.charge = met_charges[i]
        if met_formulas:
            new_metabolite.formula = met_formulas[i]
        if met_inchis:
            new_metabolite.inchi = met_inchis[i]
        new_metabolites.append(new_metabolite)
    mat_parse_annotations(new_metabolites, m, d_replace=DICT_MET)
    mat_parse_notes(new_metabolites, m, d_replace=DICT_MET_NOTES)
    model.add_metabolites(new_metabolites)

    if "genes" in dtype_names:
        gene_names = None
        gene_ids = _cell_to_str_list(m["genes"][0, 0])
        # Jelle Bonthuis 2025-01-22: added geneShortNames fallback.
        if "geneNames" in dtype_names:
            gene_names = _cell_to_str_list(m["geneNames"][0, 0])
        elif "geneShortNames" in dtype_names:
            gene_names = _cell_to_str_list(m["geneShortNames"][0, 0])
        new_genes = [
            Gene(gene_ids[i], name=gene_names[i]) if gene_names else Gene(gene_ids[i])
            for i in range(len(gene_ids))
        ]
        mat_parse_annotations(cast(list[Object], new_genes), m, d_replace=DICT_GENE)
        for current_gene in new_genes:
            current_gene._model = model
        model.genes += new_genes

    new_reactions = []
    rxn_ids = _cell_to_str_list(m["rxns"][0, 0])
    if "rxnECNumber" in dtype_names:
        rxn_EC_number = _cell_to_str_list(m["rxnECNumber"][0, 0], empty_value=None)
    else:
        rxn_EC_number = [None for _ in rxn_ids]
    rxn_lbs = _cell_to_float_list(m["lb"][0, 0], empty_value=None, inf_value=inf)
    rxn_ubs = _cell_to_float_list(m["ub"][0, 0], empty_value=None, inf_value=inf)
    rxn_gene_rules, rxn_names, rxn_subsystems = None, None, None
    try:
        rxn_gene_rules = _cell_to_str_list(m["grRules"][0, 0], "")
    except (IndexError, ValueError) as e:
        ### Jelle Bonthuis 2025-01-22: Added try/except to catch error so that
        # the error will actually show up
        raise e
    try:
        rxn_names = _cell_to_str_list(m["rxnNames"][0, 0], "")
    except (IndexError, ValueError) as e:
        ### Jelle Bonthuis 2025-01-22: Added try/except to catch error so that
        # the error will actually show up
        raise e
    try:
        # RECON3.0 mat has an array within an array for subsystems.
        # If we find a model that has multiple subsytems per reaction, this should be
        # modified
        #### JELLE BONTHUIS 2025-02-11 Added fix as the following try would always fail
        # and no error would be shown, making it so that no subsystems would be loaded

        if m["subSystems"][0, 0][0][0].dtype.char == "O" and isinstance(
            m["subSystems"][0, 0][0][0][0], np.ndarray
        ):
            ### OLD CODE BEFORE FIX JELE BONTHUIS 2025-02-11
            # rxn_subsystems = [
            #     each_cell[0][0][0][0] if each_cell else ""
            #     for each_cell in m["subSystems"][0, 0]
            # ]

            ### FIX JELE BONTHUIS 2025-02-11
            rxn_subsystems = [each_cell[0][0][0][0] for each_cell in m["subSystems"][0, 0]]
        # Other matlab files seem normal.
        else:
            rxn_subsystems = _cell_to_str_list(m["subSystems"][0, 0], "")
    except (IndexError, ValueError) as e:
        ### Jelle Bonthuis 2025-01-22: Added try/except to catch error so that
        # the error will actually show up
        raise e
    for i in range(len(rxn_ids)):
        new_reaction = Reaction(
            id=rxn_ids[i],
            lower_bound=rxn_lbs[i],
            upper_bound=rxn_ubs[i],
        )
        if rxn_names:
            new_reaction.name = rxn_names[i]
        if rxn_subsystems:
            new_reaction.subsystem = rxn_subsystems[i]
        if rxn_gene_rules:
            new_reaction.gene_reaction_rule = rxn_gene_rules[i]
        if rxn_EC_number:
            new_reaction.EC_number = rxn_EC_number[i]
        new_reactions.append(new_reaction)
    mat_parse_annotations(new_reactions, m, d_replace=DICT_REACTION)
    # TODO - When cobrapy.notes are revised not be a dictionary (possibly when
    #  annotations are fully SBML compliant, revise this function.
    mat_parse_notes(new_reactions, m, d_replace=DICT_REACTION_NOTES)

    csc = csc_matrix(m["S"][0, 0])
    for i in range(csc.shape[1]):
        stoic_dict = {model.metabolites[j]: csc[j, i] for j in csc.getcol(i).nonzero()[0]}
        new_reactions[i].add_metabolites(stoic_dict)

    model.add_reactions(new_reactions)

    # Make subsystems into groups
    if rxn_subsystems:
        rxn_group_names = set(rxn_subsystems).difference({None})
        new_groups = []
        for g_name in sorted(rxn_group_names):
            group_members = model.reactions.query(
                lambda x: x.subsystem == g_name  # noqa: B023
            )
            new_group = Group(id=g_name, name=g_name, members=group_members, kind="partonomy")
            new_group.annotation["sbo"] = "SBO:0000633"
            new_groups.append(new_group)
        model.add_groups(new_groups)

    if "c" in dtype_names:
        c_vec = _cell_to_float_list(m["c"][0, 0])
        coefficients = dict(zip(new_reactions, c_vec, strict=False))
        if model.solver is not None:
            set_objective(model, coefficients)
    else:
        logger.warning("Objective vector `c` not found.")

    if "osenseStr" in dtype_names:
        if isinstance(m["osenseStr"][0, 0][0], np.str_):
            model.objective_direction = str(m["osenseStr"][0, 0][0])
        elif isinstance(m["osenseStr"][0, 0][0], np.ndarray):
            model.objective_direction = str(m["osenseStr"][0, 0][0][0])
    elif "osense" in dtype_names:
        osense = float(m["osense"][0, 0][0][0])
        objective_direction_str = "max"
        if osense == 1:
            objective_direction_str = "min"
        model.objective_direction = objective_direction_str
    return model


def _reaction_to_dict(reaction: Reaction) -> OrderedDict:
    """Convert cobra Reaction to OrderedDict with metabolite coefficients.

    Handles special cases: NaN/Inf bounds converted to strings for JSON
    compatibility. Preserves metabolite links using OrderedDict for deterministic
    key ordering.

    Args:
        reaction (cobra.Reaction): Reaction to serialise.

    Returns:
        OrderedDict: Dict with required keys (id, name, metabolites, bounds)
            and optional keys (subsystem, notes, annotation, EC_number).

    Raises:
        None

    Requires:
        None

    Modifies:
        None (pure function).

    Example:
        >>> from cobra import Model, Reaction, Metabolite
        >>> from VmaxBuilder.cobrapy_overwrites.cobrapy_io import _reaction_to_dict
        >>> rxn = Reaction('R1')
        >>> rxn.name = 'Reaction 1'
        >>> rxn_dict = _reaction_to_dict(rxn)
        >>> rxn_dict['id']
        'R1'
    """
    new_reaction = OrderedDict()
    for key in _REQUIRED_REACTION_ATTRIBUTES:
        if key != "metabolites":
            if key == "lower_bound" and (
                np.isnan(reaction.lower_bound) or np.isinf(reaction.lower_bound)
            ):
                new_reaction[key] = str(_fix_type(getattr(reaction, key)))
            elif key == "upper_bound" and (
                np.isnan(reaction.upper_bound) or np.isinf(reaction.upper_bound)
            ):
                new_reaction[key] = str(_fix_type(getattr(reaction, key)))
            else:
                new_reaction[key] = _fix_type(getattr(reaction, key))
            continue
        mets = OrderedDict()
        for met in sorted(reaction.metabolites, key=attrgetter("id")):
            mets[str(met)] = reaction.metabolites[met]
        new_reaction["metabolites"] = mets
    _update_optional(
        reaction,
        new_reaction,
        _OPTIONAL_REACTION_ATTRIBUTES,
        _ORDERED_OPTIONAL_REACTION_KEYS,
    )
    return new_reaction


def model_to_dict(model: Model, sort: bool = False) -> OrderedDict:
    """Convert cobra Model to OrderedDict suitable for JSON serialisation.

    Converts all metabolites, reactions, genes with optional sorting. Preserves
    model attributes (id, name, notes, compartments, annotation).

    Args:
        model (cobra.Model): Model to convert.
        sort (bool, optional): If True, sort mets/reactions/genes by ID for
            consistent output. Defaults to False.

    Returns:
        OrderedDict: Dict with keys: metabolites (list), reactions (list),
            genes (list), id, name, notes, compartments, annotation.

    Raises:
        None

    Requires:
        None

    Modifies:
        None (pure function).

    Example:
        >>> from cobra import Model, Reaction, Metabolite
        >>> from VmaxBuilder.cobrapy_overwrites.cobrapy_io import model_to_dict
        >>> model = Model('test_model')
        >>> met1 = Metabolite('m1', compartment='c')
        >>> rxn1 = Reaction('r1')
        >>> rxn1.add_metabolites({met1: -1})
        >>> model.add_reactions([rxn1])
        >>> model_dict = model_to_dict(model)
        >>> model_dict['id']
        'test_model'
    """
    obj = OrderedDict()
    obj["metabolites"] = list(map(_metabolite_to_dict, model.metabolites))
    obj["reactions"] = list(map(_reaction_to_dict, model.reactions))
    obj["genes"] = list(map(_gene_to_dict, model.genes))
    obj["id"] = model.id
    _update_optional(model, obj, _OPTIONAL_MODEL_ATTRIBUTES, _ORDERED_OPTIONAL_MODEL_KEYS)
    if sort:
        get_id = itemgetter("id")
        obj["metabolites"].sort(key=get_id)
        obj["reactions"].sort(key=get_id)
        obj["genes"].sort(key=get_id)
    return obj


def model_from_dict(obj: Dict) -> Model:
    """Construct cobra Model from dictionary (inverse of model_to_dict).

    Parses metabolites, reactions, genes from dict lists. Sets objective
    from reaction coefficients. Restores model attributes.

    Args:
        obj (dict): Dict with keys: reactions (required, list), metabolites,
            genes, and optional: id, name, notes, compartments, annotation.

    Returns:
        cobra.Model: Fully constructed model ready for analysis/optimisation.

    Raises:
        ValueError: obj missing 'reactions' key.

    Requires:
        None

    Modifies:
        None (pure function).

    Example:
        >>> from VmaxBuilder.cobrapy_overwrites.cobrapy_io import model_from_dict
        >>> model_dict = {
        ...     'id': 'test',
        ...     'metabolites': [],
        ...     'reactions': [],
        ...     'genes': [],
        ... }
        >>> model = model_from_dict(model_dict)
        >>> model.id
        'test'
    """
    if "reactions" not in obj:
        raise ValueError("Object has no .reactions attribute. Cannot load.")
    model = Model()
    model.add_metabolites(
        [_metabolite_from_dict(metabolite) for metabolite in obj["metabolites"]]
    )
    model.genes.extend([gene_from_dict(gene) for gene in obj["genes"]])
    model.add_reactions(
        [_reaction_from_dict(reaction, model) for reaction in obj["reactions"]]
    )
    objective_reactions = [
        rxn for rxn in obj["reactions"] if rxn.get("objective_coefficient", 0) != 0
    ]
    coefficients = {
        model.reactions.get_by_id(rxn["id"]): rxn["objective_coefficient"]
        for rxn in objective_reactions
    }
    set_objective(model, coefficients)
    for k, v in obj.items():
        if k in {"id", "name", "notes", "compartments", "annotation"}:
            setattr(model, k, v)
    return model


def save_json_model(  # noqa: C901
    model: "Model",
    filename: Union[str, Path, IO],
    sort: bool = False,
    pretty: bool = False,
    recursive_call: bool = False,
    **kwargs: Any,
) -> None:
    """Serialise cobra Model to JSON file with NaN/Inf/int64 handling.

    Converts model to OrderedDict via model_to_dict(), then to JSON with special
    handling for non-compliant values: NaN/Inf → None, int64 → int. Retries
    recursively after fixing invalid values. Critical for models with computational
    artefacts (e.g., MATLAB import).

    Args:
        model (cobra.Model): Model to save.
        filename (str | Path | IO): Output file path or file handle.
        sort (bool, optional): Sort mets/reactions/genes by ID for consistent
            output. Defaults to False.
        pretty (bool, optional): Human-readable formatting (indent, separators).
            Defaults to False (compact).
        recursive_call (bool, optional): Internal flag for recursion after fixing
            invalid values. Defaults to False.
        **kwargs (Any): Passed to json.dump (e.g., indent, separators).

    Returns:
        None

    Raises:
        RuntimeError: NaN/int64 values present and recursive fix attempted
            but still failed (should not happen).

    Requires:
        json.dump, model_to_dict

    Modifies:
        File system: writes JSON to filename
        Model state: may set NaN/int64 fields to None/int on recursive call

    Example:
        >>> from cobra import Model
        >>> from VmaxBuilder.cobrapy_overwrites import cobrapy_io
        >>> model = Model('test')
        >>> cobrapy_io.save_json_model(model, 'output.json', pretty=True)  # doctest: +SKIP
    """
    obj = model_to_dict(model, sort=sort)
    obj["version"] = JSON_SPEC

    dump_opts: dict[str, Any]
    if pretty:
        dump_opts = {
            "indent": 4,
            "separators": (",", ": "),
            "sort_keys": True,
            "allow_nan": False,
        }
    else:
        dump_opts = {
            "indent": 0,
            "separators": (",", ":"),
            "sort_keys": False,
            "allow_nan": False,
        }
    dump_opts.update(**kwargs)
    # Cast to Any so ty treats each unpacked kwarg as Any rather than the
    # union of literal value types (int | tuple[str, str] | bool).
    _dump_opts: Any = dump_opts

    #### Jelle Bonthuis 2025-01-22: Added try/except to catch Na and NaN values
    try:
        if isinstance(filename, (str, Path)):
            with open(filename, "w") as file_handle:
                json.dump(obj, file_handle, **_dump_opts)
        else:
            json.dump(obj, filename, **_dump_opts)
    except ValueError as e:
        if "Out of range float values are not JSON compliant: nan" in str(e):
            if recursive_call:
                raise RuntimeError(
                    "Error saving model to JSON: NaN values in model."
                    "And already tried to fix them. But still not JSON compliant."
                ) from e
            logger.warning("Some values in model not JSON compliant. Setting them to None.")
            for reaction in model.reactions:
                for field in reaction.__dict__:
                    try:
                        if (
                            field in _REACTION_FIELDS_TO_CHECK
                            and not isinstance(getattr(reaction, field), str)
                            and (
                                getattr(reaction, field) in ["Na", "NaN"]
                                or np.isnan(getattr(reaction, field))
                            )
                        ):
                            setattr(reaction, field, None)
                    except Exception:
                        pass

            for metabolite in model.metabolites:
                for field in metabolite.__dict__:
                    try:
                        if (
                            field in _META_FIELDS_TO_CHECK
                            and not isinstance(getattr(metabolite, field), str)
                            and (
                                getattr(metabolite, field) in ["Na", "NaN"]
                                or np.isnan(getattr(metabolite, field))
                            )
                        ):
                            setattr(metabolite, field, None)
                    except Exception:
                        pass

            for gene in model.genes:
                for field in gene.__dict__:
                    try:
                        if (
                            field in _GENE_FIELDS_TO_CHECK
                            and not isinstance(getattr(gene, field), str)
                            and (
                                getattr(gene, field) in ["Na", "NaN"]
                                or np.isnan(getattr(gene, field))
                            )
                        ):
                            setattr(gene, field, None)
                    except Exception:
                        pass
            save_json_model(
                model, filename, sort=sort, pretty=pretty, recursive_call=True, **kwargs
            )

        elif "of type int64 is not JSON serializable" in str(e):
            if recursive_call:
                raise RuntimeError(
                    "Error saving model to JSON: int64 values in model."
                    "And already tried to fix them. But still not JSON compliant."
                ) from e
            logger.warning(
                "Some values in model are int64; converting to int for JSON serialisation."
            )
            for reaction in model.reactions:
                for field in reaction.__dict__:
                    try:
                        if (
                            field in _REACTION_FIELDS_TO_CHECK
                            and not isinstance(getattr(reaction, field), str)
                            and isinstance(getattr(reaction, field), np.int64)
                        ):
                            setattr(reaction, field, int(getattr(reaction, field)))
                    except Exception:
                        pass
            for metabolite in model.metabolites:
                for field in metabolite.__dict__:
                    try:
                        if (
                            field in _META_FIELDS_TO_CHECK
                            and not isinstance(getattr(metabolite, field), str)
                            and isinstance(getattr(metabolite, field), np.int64)
                        ):
                            setattr(metabolite, field, int(getattr(metabolite, field)))
                    except Exception:
                        pass
            for gene in model.genes:
                for field in gene.__dict__:
                    try:
                        if (
                            field in _GENE_FIELDS_TO_CHECK
                            and not isinstance(getattr(gene, field), str)
                            and isinstance(getattr(gene, field), np.int64)
                        ):
                            setattr(gene, field, int(getattr(gene, field)))
                    except Exception:
                        pass
            save_json_model(
                model, filename, sort=sort, pretty=pretty, recursive_call=True, **kwargs
            )
        else:
            raise RuntimeError(f"Error saving model to JSON: {e}") from e
