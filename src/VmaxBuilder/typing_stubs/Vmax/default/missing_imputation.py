from dataclasses import dataclass


@dataclass
class MissingReactionImputationConfigProtocol:
    method_GPR_promiscuity_method = False
    method_should_impute_expressionless_reactions = True
    method_GPRless_reaction_method = "substrate_producing_reaction_median"
    method_GPRless_minimum_amount_of_reactions_threshold = 8
    method_GPRless_reaction_method_2 = "reaction_median"
    method_GPRless_transport_method = "transport_reactions_median"
