# todo: show how many IFPs actually have enough values to even be trimmable

# show how many IFPs actually have enough values to be trimmable and have at least 1
# trimmable gene

# show how many IFPs are trimmed once or more times in this specific expression dataset

# show of all IFPs that are trimmed once, their percentage of samples they are
# trimmed in (bar)

# show amount of samples per IFP (histogram with x asis the IFPs and the amount of )
# show amount of IPFs per sample (same as above but x axis is the samples)
# todo: think of plot where one can show whether samples share specific IFPs ->
# heatmap with trues falses for each sample and each IFP, then clustering
# also UpSet plot for the same, but with the IFPs as sets and the samples as
# elements in the sets

# last we could also try jaccard similarity between samples, samples with high similarity
# indicate they share same IFPs
# and/or same for between IFPs

# todo: total amount of trimming

# ensure that IFPs that are trimmed can be traced back to their real IFP
# todo: ensure that old version and new version give similar output
import cobra.io.mat
from cobra.core.model import Model
from cobra.io.json import load_json_model

from VmaxBuilder.cobrapy_overwrites.cobrapy_io import load_matlab_model
from VmaxBuilder.utils.extra_utils import remove_compartment

if __name__ == "__main__":
    from pathlib import Path

    # pkl_path = Path(
    #     r"/home/p70088775/git/VmaxBuilder/data"
    #     "/run_example_output/NCI_60_human_run/artifacts/Vmax_stage/"
    #     "IFP_sample_abundance_dict.pkl"
    # )
    # import pickle
    # from time import perf_counter
    #
    # time_start = perf_counter()
    # with open(pkl_path, "rb") as f:
    #     data = pickle.load(f)
    # time_end = perf_counter()
    #
    # print(f"total_time_elapsed:{time_end - time_start}")

    def get_all_gene_substrate_combinations(model: Model):
        gene_substrate_combinations = {}
        for reaction in model.reactions:
            if not reaction.genes:
                continue
            substrates = reaction.metabolites
            substrates = {
                remove_compartment(met.id): stoich
                for met, stoich in substrates.items()
                if stoich < 0
            }

            for gene in reaction.genes:
                if not gene:
                    continue
                gene = gene.id

                if gene not in gene_substrate_combinations:
                    gene_substrate_combinations[gene] = set()
                for substrate in substrates:
                    gene_substrate_combinations[gene].add(substrate)

        return gene_substrate_combinations

    model_dir = Path(r"/home/p70088775/git/SWAPAM/data/for_SWAMP/models/")
    human_2 = (
        r"/home/p70088775/git/SWAPAM/data/for_SWAMP"
        "/models/Human-GEM-2.0.0/model/Human-GEM.mat"
    )
    human_1_17 = model_dir / "HumanGem17_irreversible" / "reversible_cobra_model.json"
    # load

    human_2 = cobra.io.mat.load_matlab_model(human_2)
    hum_2_all_gene_substrate_combinations = get_all_gene_substrate_combinations(human_2)

    human_1_17 = load_json_model(str(human_1_17))
    hum_1_17_all_gene_substrate_combinations = get_all_gene_substrate_combinations(human_1_17)

    # compare the two, we want to find any that are in the 1.17 model but not in the 2.0
    # model, we ddo not care about the other way around,

    missing_genes = set()
    for gene, _substrates in hum_1_17_all_gene_substrate_combinations.items():
        if gene not in hum_2_all_gene_substrate_combinations:
            missing_genes.add(gene)

    print(f"total_genes_in_human_1_17_model: {len(hum_1_17_all_gene_substrate_combinations)}")
    print(f"total_genes_in_human_2_model: {len(hum_2_all_gene_substrate_combinations)}")
    print(f"total_missing_genes: {len(missing_genes)}")

    # now we also need to check the actual substrate gene combinations, so we need to check
    # if the substrates are the same for each gene, if not we need to report that as well
    # this means that if we had x-A x-B etc, we think of each combination as its own entity
    # we want to find all such combinations that are not in the 1.17 model (as we already
    # calculated kcats for the 1.17 model, we just want to find what extra we need to
    # calculate kcats for in the 2.0 model)

    missing_gene_substrate_combinations = {}
    for gene, substrates in hum_1_17_all_gene_substrate_combinations.items():
        if gene not in hum_2_all_gene_substrate_combinations:
            missing_gene_substrate_combinations[gene] = substrates
        else:
            # check if the substrates are the same
            missing_substrates = substrates - hum_2_all_gene_substrate_combinations[gene]
            if missing_substrates:
                missing_gene_substrate_combinations[gene] = missing_substrates

    print(
        f"total_missing_gene_substrate_combinations: "
        f"{len(missing_gene_substrate_combinations)}"
    )
    # any duplicate metabolite name without compartment does tn

    pass
