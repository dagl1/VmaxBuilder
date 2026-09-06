from dataclasses import dataclass


@dataclass
class UniKPConfig:
    chunk_size: int = 200
    embedding_batch_size: int = 50
    embedding_cache_save_every_batches: int = 1
    prediction_checkpoint_every_chunks: int = 5
    amount_of_smiles_replicates: int = 50
    type_of_smiles: str = "isomeric_SMILES"
