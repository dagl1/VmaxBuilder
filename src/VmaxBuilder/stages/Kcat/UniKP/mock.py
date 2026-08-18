from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from VmaxBuilder.utils.file_handling import get_project_root


@dataclass(frozen=True)
class KcatPaths:
    output_dir: Path
    smiles_file: Path
    sequence_file: Path
    gene_metabolite_pairs_file: Path
    gene_metabolite_pairs_legacy_file: Path
    sequence_tensor_cache_file: Path
    smiles_tensor_cache_file: Path
    predictions_csv_file: Path
    predictions_json_file: Path
    missing_csv_file: Path


def mock_infer_kcats(
    smiles_df: pd.DataFrame,
    transcript_df: pd.DataFrame,
    gene_substrate_paris: dict[str, set[str]],
    chunk_size: int = 200,
    embedding_batch_size: int = 50,
    embedding_cache_save_every_batches: int = 1,
    prediction_checkpoint_every_chunks: int = 10,
    amount_of_smiles_replicates: int = 50,
    type_of_smiles: str = "isomeric SMILES",
) -> tuple[KcatPaths, pd.DataFrame]:
    root = get_project_root()
    external = root / "external"

    return (
        KcatPaths(
            output_dir=external / "kcat_predictions",
            smiles_file=external / "kcat_predictions" / "SMILES_df.csv",
            sequence_file=external / "kcat_predictions" / "transcript_df.csv",
            gene_metabolite_pairs_file=external
            / "kcat_predictions"
            / "gene_metabolite_pairs.json",
            gene_metabolite_pairs_legacy_file=external
            / "kcat_predictions"
            / "gene_metabolite_pairs_legacy.json",
            sequence_tensor_cache_file=external
            / "kcat_predictions"
            / "sequence_tensor_cache.pt",
            smiles_tensor_cache_file=external / "kcat_predictions" / "smiles_tensor_cache.pt",
            predictions_csv_file=external / "kcat_predictions" / "predictions.csv",
            predictions_json_file=external / "kcat_predictions" / "predictions.json",
            missing_csv_file=external / "kcat_predictions" / "missing.csv",
        ),
        pd.DataFrame(
            {
                "gene": ["gene1", "gene2", "gene3"],
                "substrate": ["substrate1", "substrate2", "substrate3"],
                "predicted_kcat": [1.0, 2.0, 3.0],
                "confidence": [0.9, 0.8, 0.95],
            }
        ),
    )
