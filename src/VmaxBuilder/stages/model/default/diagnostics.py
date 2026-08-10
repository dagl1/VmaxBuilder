class ModelDiagnostics:
    # todo:
    # alluvial plot for reactions [(exchange, active_transport, diffusion_transport, regular),
    # (compartment or multi-compartment),
    # (single gene, (multi-gene: only OR, only AND, mixed
    # ANDC/OR) , gprless),
    # (reverisble, irreverisble),
    # (subsystem)]

    # todo: metabolite alluvial for metabolites [(missing smiles, present smiles),
    # ( compartments),
    #  (output reactions 2, 2, 3, <=10, >10), (input reactions 1, 2, 3, <=10, >10),
    # (total reactions 1, 2, 3, <=10, >10), (present in n_other_compartments)]
    # )
    def before_run(self, scaffold, config):
        print("starting model stage")

    def after_run(self, scaffold, config):
        print("finished model stage")
