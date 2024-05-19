from unified_planning.shortcuts import PlanValidator, SequentialSimulator

from pypmt.planner.plan.smt_sequential_plan import SMTSequentialPlan


def __iter__(self):
    return iter(self.plan.actions)

def __init__(self, plan, task, z3_plan, actions_sequence):
    self.behaviour  = None
    self.isvalid    = None
    self.cost_value = None
    self.id        = None
    self._z3_plan  = z3_plan
    self.validation_fail_reason = None
    self.actions_sequence = actions_sequence
    self.plan = plan
    self.task = task

setattr(SMTSequentialPlan, '__iter__', __iter__)
setattr(SMTSequentialPlan, '__init__', __init__)