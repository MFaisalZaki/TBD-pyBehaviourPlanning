from collections import defaultdict
import z3

from z3 import ModelRef
from unified_planning.plans import SequentialPlan

from behaviour_planning_smt.bss.behaviour_features_library.cost_bound import CostBound

class MakespanOptimalCostBound(CostBound):
    def __init__(self, encoder, additional_information):
        self.disable_action_check = additional_information.get('disable_action_check', False)
        super().__init__('makespan-optimal-cost-bound', encoder, lambda a: 1, additional_information)

    def __encode__(self, encoder):
        # Call the base encodings for the cost bound dimension.
        super().__encode__(encoder)

        if self.disable_action_check: return

        # TODO: we need to find a quick way to encode the makespan.
        for t, goal_state in enumerate(encoder.goal_states):
            # Can we do this with setting the actions to False?!
            after_goal_state_actions = []
            for t2 in range(t+1, len(encoder)):
                after_goal_state_actions.extend(self.actions_costs_vars[t2])
            self.encodings.append(goal_state == (z3.Sum(after_goal_state_actions) == z3.IntVal(0, ctx=encoder.ctx)))
        
    def value(self, plan):
        retvalue = None
        if isinstance(plan, ModelRef):
            retvalue = plan.evaluate(self.var, model_completion = True)
        elif isinstance(plan, SequentialPlan):
            assert False, 'Value function is not implemented for this dimension for a plan.'
        else:
            raise TypeError(f"Unknown type for plan: {type(plan)}")
        self.var_domain.add(str(retvalue))
        return retvalue

    def discretize(self, value):
        return value.as_long()
