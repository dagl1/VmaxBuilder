from pathlib import Path
from pickle import load

if __name__ == "__main__":
    location = (
        r"/home/p70088775/git/SWAPAM/data/for_SWAMP/combinations/"
        "PTR_model_inhouse_v9_human_Bastien_cardio_collab_samples_tasklist_MACSBIO_v0_6_6_20260210_Eraslan2019_human_UniKPV1"  # noqa # pragma: allowlist secret
        "/sample_IFE_contribution_to_reaction_dict.pkl"
    )
    path = Path(location)
    with open(path, "rb") as f:
        data = load(f)

    print(f"Loaded data from {path}:")
    print(data)
