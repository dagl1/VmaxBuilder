from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pandas as pd
from cobra.core.model import Model
from cobra.io.json import load_json_model
from rdkit import Chem

from VmaxBuilder.base.classes import BaseImplementation, DiagnosticOutputSpec
from VmaxBuilder.base.configs import FullConfig, InputSpec, OutputSpec, Scaffold
from VmaxBuilder.GPR.gpr_preprocessing import (
    build_gene_to_IFP_mapping,
    build_gene_to_transcripts_mapping,
    build_IFP_mapping_from_gpr_rules,
    build_reaction_to_IFP_mapping,
    clear_simplification_cache,
    expand_gene_IFP_to_transcript_IFPs,
    get_simplification_cache_info,
    get_unique_genes_from_IFP_mapping,
    get_unique_gpr_rules,
)
from VmaxBuilder.Kcat_preprocessing.gene_substrate_preprocessing import (
    get_gene_substrate_mapping,
)
from VmaxBuilder.utils.extra_utils import remove_compartment


def inchi_to_smiles(inchi, isomeric=True):
    if pd.isna(inchi) or not str(inchi).strip():
        return None
    # Convert InChI to an RDKit Molecule Object
    mol = Chem.MolFromInchi(str(inchi))
    if mol:
        # Convert Molecule to Isomeric or Canonical SMILES
        return Chem.MolToSmiles(mol, isomericSmiles=isomeric)
    return "Invalid InChI"


def smiles_to_inchi(smiles):
    if pd.isna(smiles) or not str(smiles).strip():
        return None
    # Convert SMILES to an RDKit Molecule Object
    mol = Chem.MolFromSmiles(str(smiles))
    if mol:
        # Convert Molecule to InChI
        return Chem.MolToInchi(mol)
    return "Invalid SMILES"


def function_for_identifying_novel_found_SMILES_and_only_doing_those(
    old_SMILES_df: pd.DataFrame,
    new_SMILES_df: pd.DataFrame,
):
    pass


class TranscriptSMILESGetter(BaseImplementation[FullConfig]):
    STAGE_NAME: str = "model"  # while necessary for kcat, it really is based on the model
    IMPL_NAME: str = "SMILES_transcript_getter"
    INPUTS: list[InputSpec] = [
        InputSpec(
            name="cobra_model",
            data_type=Model,
            in_scaffold=True,
        ),
        InputSpec(
            name="cobra_model_data",
            data_type=pd.DataFrame,
            prefix="model_data",  # for SysBioChalmers models (Human1 etc. ) this is
            # often a .xlsx file with multiple sheets. Rename it to avoid confusion
            extensions=[".csv", ".xlsx"],
        ),
        InputSpec(
            name="genes_df",
            data_type=pd.DataFrame,
            prefix="model_genes",  # for SysBioChalmers models (Human1 etc. ) this is
            # often a .xlsx file with multiple sheets. Rename it to avoid confusion
            extensions=[".tsv", ".csv", ".xlsx"],
        ),
        InputSpec(
            name="metabolites_df",
            data_type=pd.DataFrame,
            prefix="model_metabolites",  # for SysBioChalmers models (Human1 etc. ) this is
            # often a .xlsx file with multiple sheets. Rename it to avoid confusion
            extensions=[".tsv", ".csv", ".xlsx"],
        ),
        InputSpec(
            name="SMILES_df",
            data_type=pd.DataFrame,
            optional=True,
        ),
        InputSpec(
            name="manually_curated_SMILES_df",
            data_type=pd.DataFrame,
            optional=True,
        ),
        InputSpec(
            name="metabolites_SMILES_Inchi_df",
            data_type=pd.DataFrame,
            optional=True,
            extensions=[
                ".tsv",
            ],
        ),
        InputSpec(
            name="transcript_df",
            data_type=pd.DataFrame,
            optional=True,
        ),
    ]
    OUTPUTS: list[OutputSpec] = [
        OutputSpec(
            name="SMILES_df",
            data_type=pd.DataFrame,
            scaffold_location="artifacts",
            save_file_name="SMILES_df",
            extension=".csv",
            validator=None,
        ),
        OutputSpec(
            name="transcript_df",
            data_type=pd.DataFrame,
            scaffold_location="diagnostics",
            save_file_name="transcript_df",
            extension=".csv",
            validator=None,
        ),
        OutputSpec(
            "gene_substrate_mapping",
            data_type=dict[str, set[str]],
            scaffold_location="diagnostics",
        ),
    ]


if __name__ == "__main__":
    import json
    from pathlib import Path

    # load model
    # load model data
    # load smiles df if exitst
    # laod transcript df if exists

    base_dir = r"/home/p70088775/git/VmaxBuilder/data/run_example_output/NCI_60_human_run/"
    SWAPAM_data_dir = Path(r"/home/p70088775/git/SWAPAM/data/for_SWAMP/")
    models_dir = SWAPAM_data_dir / "models"
    model_dir = models_dir / "Human-GEM-2.0.0"
    model_file = model_dir / "model_Human-GEM.json"
    metabolites_file = model_dir / "model_metabolites.tsv"
    genes_file = model_dir / "model_genes.tsv"
    model_data_file = model_dir / "model_data_Human-GEM.xlsx"
    manually_curated_SMILES_file = model_dir / "manually_curated_SMILES.csv"
    metabolites_SMILES_Inchi_file = model_dir / "metabolites_SMILES_Inchi.tsv"

    # model_data_GENES = pd.read_excel(model_data_file, sheet_name="GENES")
    model_data_METS = pd.read_excel(model_data_file, sheet_name="METS")
    # model_genes_df = pd.read_csv(genes_file, sep="\t")
    model_metabolites_df = pd.read_csv(metabolites_file, sep="\t")
    cobra_model = load_json_model(model_file)
    metabolites_SMILES_Inchi_df = pd.read_csv(
        metabolites_SMILES_Inchi_file, sep="\t", dtype=str, na_filter=False
    )

    import csv
    from pathlib import Path

    def load_manually_curated_SMILES(
        manually_curated_SMILES_file: str | Path,
    ) -> pd.DataFrame:
        expected_columns = [
            "name",
            "id",
            "id_without_compartment",
            "base_to_work_from",
            "difference",
            "base_smiles",
            "modified_smiles",
        ]

        rows = []

        with open(
            manually_curated_SMILES_file,
            "r",
            encoding="utf-8",
            newline="",
        ) as f:
            reader = csv.reader(f)

            # Skip the original header.
            next(reader)

            for row in reader:
                # Empty line
                if not row:
                    continue

                # The first field is the name. If the name contains an
                # unquoted comma, reconstruct it from the extra fields.
                if len(row) > len(expected_columns):
                    extra_fields = len(row) - len(expected_columns) + 1

                    name = ",".join(row[:extra_fields])
                    row = [name] + row[extra_fields:]

                # Pad rows with missing trailing fields.
                row += [None] * (len(expected_columns) - len(row))

                # Reject genuinely malformed rows.
                if len(row) > len(expected_columns):
                    raise ValueError(
                        f"Malformed row with {len(row)} fields "
                        f"(expected at most {len(expected_columns)}):\n{row}"
                    )

                rows.append(row)

        return pd.DataFrame(rows, columns=expected_columns)

    gene_substrate_mapping = get_gene_substrate_mapping(
        cobra_model=cobra_model,
    )
    gene_ids = [gene.id for gene in cobra_model.genes]
    metabolite_ids = [met.id for met in cobra_model.metabolites]
    metabolite_ids_without_compartment = set(
        sorted([remove_compartment(met.id) for met in cobra_model.metabolites])
    )

    # in the SMILES_inchi file, get all inchi's
    # similarly in model_METS check for Inchi column
    # check manually_curated_SMILES_df and convert to inchi

    # print columns in each df so we can see what we have
    manually_curated_SMILES_df = pd.read_csv(
        manually_curated_SMILES_file,
        sep="\t",
        dtype=str,
    )
    print("model_data_METS columns:", model_data_METS.columns.tolist())
    print("model_metabolites_df columns:", model_metabolites_df.columns.tolist())
    print(
        "metabolites_SMILES_Inchi_df columns:", metabolites_SMILES_Inchi_df.columns.tolist()
    )
    print("manually_curated_SMILES_df columns:", manually_curated_SMILES_df.columns.tolist())
    print("manually_curated_SMILES_df columns:", manually_curated_SMILES_df.columns.tolist())
    print("manually_curated_SMILES_df head:", manually_curated_SMILES_df.head())

    # model_data_METS columns: ['#', 'ID', 'NAME', 'UNCONSTRAINED', 'MIRIAM', 'COMPOSITION',
    # 'InChI', 'COMPARTMENT', 'REPLACEMENT ID', 'CHARGE']
    # model_metabolites_df columns: ['mets', 'metsNoComp', 'metBiGGID', 'metKEGGID',
    # 'metHMDBID',
    # 'metChEBIID', 'metPubChemID', 'metLipidMapsID', 'metEHMNID', 'metHepat
    # oNET1ID', 'metRecon3DID', 'metMetaNetXID', 'metHMR2ID', 'metRetired']
    # metabolites_SMILES_Inchi_df columns: ['mets', 'metsNoComp', 'SMILES', 'inchikey',
    # 'inchi']
    # manually_curated_SMILES_df columns: ['name', 'id', 'id_without_compartment',
    # 'base_to_work_from', 'difference', 'base_smiles', 'modified_smiles']

    # always match id to whatever we want
    inchi_from_METS = model_data_METS.set_index("ID")["InChI"].to_dict()
    inchi_from_METS = {remove_compartment(k): v for k, v in inchi_from_METS.items()}
    inchi_from_metabolites_SMILES_Inchi = metabolites_SMILES_Inchi_df.set_index("mets")[
        "inchi"
    ].to_dict()
    inchi_from_metabolites_SMILES_Inchi = {
        remove_compartment(k): v for k, v in inchi_from_metabolites_SMILES_Inchi.items()
    }
    smiles_from_manually_curated_SMILES = manually_curated_SMILES_df.set_index("id")[
        "modified_smiles"
    ].to_dict()
    # # remove compartment from the keys of smiles_from_manually_curated_SMILES
    smiles_from_manually_curated_SMILES = {
        remove_compartment(k): v for k, v in smiles_from_manually_curated_SMILES.items()
    }
    #
    # # convert modified_smiles to inchi using smiles_to_inchi function
    inchi_from_manually_curated_SMILES = {
        remove_compartment(k): smiles_to_inchi(v)
        for k, v in smiles_from_manually_curated_SMILES.items()
    }
    #
    # # get only the sets of metablites without compartment
    # # and populate them with inchi, if more than one inchi (different) inhchi for the same
    # # metabolite exists, we put them in a conflict_dict and we just choose the first one
    # # for now
    conflict_dict = {}
    inchi_mapping = {}

    for met_id in metabolite_ids_without_compartment:
        for source_dict in [
            inchi_from_METS,
            inchi_from_metabolites_SMILES_Inchi,
            inchi_from_manually_curated_SMILES,
        ]:
            if met_id in source_dict:
                if met_id not in conflict_dict:
                    inchi_mapping[met_id] = set()
                inchi_mapping[met_id].add(source_dict[met_id])
                if len(inchi_mapping[met_id]) > 1:
                    conflict_dict[met_id] = inchi_mapping[met_id]

    # create a SMILES_df with columns: "name", "id", "id_without_compartment", "InChI",
    # "SMILES"
    # populate it with the inchi_mapping and convert inchi to SMILES using inchi_to_smiles
    # function
    new_SMILES_df = pd.DataFrame(
        [
            {
                "name": met_id,
                "id": met_id,
                "id_without_compartment": met_id,
                "InChI": list(inchi_mapping[met_id])[0],
                "isomeric_SMILES": inchi_to_smiles(list(inchi_mapping[met_id])[0]),
                "canonical_SMILES": inchi_to_smiles(
                    list(inchi_mapping[met_id])[0], isomeric=False
                ),
            }
            for met_id in inchi_mapping
        ]
    )
    # remove invalid SMILES rows and invalid InChI rows
    # "Invalid SMILES"
    new_SMILES_df = new_SMILES_df[
        (new_SMILES_df["isomeric_SMILES"] != "Invalid InChI")
        & (new_SMILES_df["canonical_SMILES"] != "Invalid InChI")
    ]

    # add rows for metabolites that are in the model but not in the SMILES_df,
    # with missing values for InChI and SMILES (empty values)

    new_SMILES_df = pd.concat(
        [
            new_SMILES_df,
            pd.DataFrame(
                [
                    {
                        "name": met_id,
                        "id": met_id,
                        "id_without_compartment": met_id,
                        "InChI": None,
                        "isomeric_SMILES": None,
                        "canonical_SMILES": None,
                    }
                    for met_id in metabolite_ids_without_compartment
                    if met_id not in new_SMILES_df["id_without_compartment"].values
                ]
            ),
        ],
        ignore_index=True,
    )

    # amount of missing smiles per met_without compartment
    # create 2 additional columns, missing_smiles and smiles_longer_than_218

    # missing smiles are those that are NaN in the isomeric_SMILES column or empty strings
    new_SMILES_df["missing_smiles"] = new_SMILES_df["isomeric_SMILES"].isna() | (
        new_SMILES_df["isomeric_SMILES"] == ""
    )
    new_SMILES_df["smiles_longer_than_218"] = new_SMILES_df["isomeric_SMILES"].apply(
        lambda x: len(x) > 218 if pd.notna(x) else False
    )
    new_SMILES_df.to_csv(base_dir + "SMILES_df.csv", index=False)
    # number of total rows
    # number of rows with missing smiles
    # number of rows with smiles longer than 218 characters
    print("Total rows in SMILES_df:", len(new_SMILES_df))
    print(
        "Number of rows with missing smiles:",
        new_SMILES_df["missing_smiles"].sum(),
    )
    print(
        "Number of rows with smiles longer than 218 characters:",
        new_SMILES_df["smiles_longer_than_218"].sum(),
    )
    # old amounts:
    # 3462
    # 4299
    # now -> regressed, so should likely apply the new code
    # 3024
    # 4165
    pass
