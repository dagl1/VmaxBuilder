from VmaxBuilder.base.classes import BaseStageDiagnostics

# todo: create some comprehensive: characterise list of reactions (such as those
# turned GPRless)
# todo: also create comprehensive genes - reactions (many to many) mappign and analysis


class ProteinStageDiagnostics(BaseStageDiagnostics):
    def after_run(self, scaffold):
        # Example diagnostic: Check if the output protein dataframe has expected columns
        protein_df = scaffold.get("protein_df")
        if protein_df is not None:
            expected_columns = {"protein_id", "sequence", "expression_level"}
            missing_columns = expected_columns - set(protein_df.columns)
            if missing_columns:
                raise ValueError(
                    f"Protein dataframe is missing expected columns: {missing_columns}"
                )
