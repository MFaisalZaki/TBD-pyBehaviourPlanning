from collections import defaultdict
import z3

from bss.behaviour_features_library.base import DimensionConstructor

class CostBound(DimensionConstructor):
    def __init__(self, name, encoder, action_cost_fn, additional_information):
        self.action_cost_fn     = action_cost_fn
        self.actions_costs_vars = defaultdict(dict)
        super().__init__(name, encoder, additional_information)

    def __encode__(self, encoder):
        self.actions_cost = z3.Int(self.name, ctx=encoder.ctx)
        self.var        = self.actions_cost

        all_actions    = []
        for t in range(0, len(encoder)):
            self.actions_costs_vars[t] = [z3.If(a, z3.IntVal(self.action_cost_fn(a), ctx=encoder.ctx), \
                                                   z3.IntVal(0, ctx=encoder.ctx)) \
                                        for a in encoder.get_actions_vars(t)]
            all_actions += self.actions_costs_vars[t]
        
        self.encodings.append(self.actions_cost == z3.Sum(all_actions))
        self.encodings.append(self.actions_cost >  z3.IntVal(0, ctx=encoder.ctx))
        self.encodings.append(self.actions_cost <= z3.IntVal(len(encoder), ctx=encoder.ctx))

        for t in range(1, len(encoder)):
            self.encodings.append(z3.Implies(z3.Or(encoder.get_actions_vars(t)), \
                                             z3.PbEq([(a, 1) for a in encoder.get_actions_vars(t-1)], 1)))
    
    def discretize(self, value):
        return value.as_long()
    
