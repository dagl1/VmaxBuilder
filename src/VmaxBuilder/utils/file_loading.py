from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from pickle import load as pickle_load

import pandas as pd
from pyreadr import read_r


@dataclass
class LoadContext:
    index_col: int | str | None = None


def load_csv(location: Path, context: LoadContext) -> pd.DataFrame:
    index_col = context.index_col
    return pd.read_csv(location, index_col=index_col)


def load_tsv(location: Path, context: LoadContext) -> pd.DataFrame:
    index_col = context.index_col
    return pd.read_csv(location, sep="\t", index_col=index_col)


def load_json(location: Path, context: LoadContext) -> object:
    with open(location, "r", encoding="utf-8") as json_file:
        data = json.load(json_file)
    try:
        return pd.DataFrame(data)
    except ValueError:
        return data


def load_pickle(location: Path, context: LoadContext) -> object:
    with open(location, "rb") as pickle_file:
        data = pickle_load(pickle_file)
    try:
        return pd.read_pickle(location)
    except ValueError:
        return data


def load_xlsx(location: Path, context: LoadContext) -> pd.DataFrame:
    return pd.read_excel(location)


def load_feather(location: Path, context: LoadContext) -> pd.DataFrame:
    return pd.read_feather(location)


def load_parquet(location: Path, context: LoadContext) -> pd.DataFrame:
    return pd.read_parquet(location)


def load_rds(location: Path, context: LoadContext) -> pd.DataFrame:
    result = read_r(str(location))
    if len(result) == 1:
        return next(iter(result.values()))

    # find something that looks like a dataframe
    for value in result.values():
        try:
            pd.DataFrame(value)
            return pd.DataFrame(value)
        except Exception:
            continue
    raise ValueError(f"Could not find a dataframe in the RDS file at {location}")


def load_cobra_model(location: Path, context: LoadContext) -> object:
    from cobra.io import load_json_model, load_matlab_model, load_yaml_model, read_sbml_model

    location_path = Path(location)
    if location_path.suffix == ".json":
        return load_json_model(str(location_path))
    if location_path.suffix == ".xml":
        return read_sbml_model(str(location_path))
    if location_path.suffix == ".mat":
        return load_matlab_model(str(location_path))
    if location_path.suffix == ".yaml" or location_path.suffix == ".yml":
        return load_yaml_model(str(location_path))
    if location_path.suffix == ".sbml":
        return read_sbml_model(str(location_path))
    raise ValueError(f"Unsupported COBRA model file extension for {location_path}")
