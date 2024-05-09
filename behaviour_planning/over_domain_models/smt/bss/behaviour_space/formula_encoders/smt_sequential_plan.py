
from unified_planning.shortcuts import PlanValidator, SequentialSimulator
from unified_planning.io import PDDLWriter
from unified_planning.engines.sequential_simulator import evaluate_quality_metric, evaluate_quality_metric_in_initial_state
from unified_planning.model.metrics import MinimizeSequentialPlanLength

class SMTSequentialPlan:
    def __init__(self, plan, task, z3_plan, actions_sequence):
        self.task      = task
        self.behaviour  = None
        self.isvalid    = None
        self.cost_value = None
        self.id        = None
        self._z3_plan  = z3_plan
        self.validation_fail_reason = None
        self.actions_sequence = actions_sequence
        self.plan = plan

    def __len__(self):
        return len(self.plan.actions)
    
    def __iter__(self):
        return iter(self.plan.actions)

    def __str__(self):
        return PDDLWriter(self.task).get_plan(self.plan)

    def cost(self):
        # TODO: We need to check the task if it has a metric or not.
        # Check the example in https://github.com/aiplan4eu/unified-planning/blob/1bea6799cbf1217ca6d45540b9ce68a1e0eb2106/docs/notebooks/08-sequential-simulator.ipynb#L486
        plan_length = MinimizeSequentialPlanLength()
        with SequentialSimulator(problem=self.task) as simulator:            
            initial_state = simulator.get_initial_state()
            current_state = initial_state
            states = [current_state]
            for action_instance in self.plan.actions:
                current_state = simulator.apply(current_state, action_instance)
                if current_state is None: 
                    assert False, "No cost available since the plan is invalid."
                states.append(current_state)

            plan_length_value = evaluate_quality_metric_in_initial_state(simulator, plan_length)
            current_state = states[0]
            for next_state, action_instance in zip(states[1:], self.plan.actions):
                plan_length_value = evaluate_quality_metric(
                    simulator, 
                    plan_length, 
                    plan_length_value,
                    current_state,
                    action_instance.action,
                    action_instance.actual_parameters,
                    next_state
                )
                current_state = next_state
            
            # TODO: update the self.cost_value with the plan_length_value if there is no metric available in the task.
            self.cost_value = plan_length_value
        return self.cost_value
    
    def validate(self):
        """!
        Validates plan (when one is found).

        @param domain: path to PDDL domain file.
        @param problem: path to PDDL problem file.

        @return plan: string containing plan if plan found is valid, None otherwise.
        """
        if self.plan is None or self.task is None:
            self.validation_fail_reason = "No plan or task provided." 
            return None
        if self.isvalid is not None: return self.isvalid
        
        with PlanValidator() as validator:
            validationresult = validator.validate(self.task, self.plan)
        self.validation_fail_reason = validationresult.reason
        self.isvalid = validationresult.status.value == 1 if validationresult else False
        return self.isvalid