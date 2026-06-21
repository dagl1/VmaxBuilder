class ModelDiagnostics:
    def before_run(self, scaffold, config):
        print("starting model stage")

    def after_run(self, scaffold, config):
        print("finished model stage")
