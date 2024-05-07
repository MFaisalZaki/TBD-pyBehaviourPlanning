
from collections import defaultdict

from z3 import *

from unified_planning.plans import SequentialPlan

from bss.behaviour_space.formula_encoders.linear_formula_encoder import EncoderSequential
from bss.behaviour_space.formula_encoders.smt_sequential_plan import SMTSequentialPlan

from bss.behaviour_features_library.makespan_optimal_cost_bound import MakespanOptimalCostBound

class BehaviourSpace:
    def __init__(self, task, cfg=defaultdict(dict)) -> None:
        self.task    = task
        self.encoder = EncoderSequential(task)

        self.upper_bound            = cfg.get('upper-bound', 100)
        self.run_plan_validation    = cfg.get('run-plan-validation', False)
        
        self._behaviour_frequency = defaultdict(dict)
        self._plans = []

        self.encoder.encode(self.upper_bound)
        
        self.dims  = cfg.get('dims', [])
        if MakespanOptimalCostBound not in [d[0] for d in self.dims]:
            self.dims += [(MakespanOptimalCostBound, {})]
        
        self.dims  = [d(self.encoder, additional_information) for d, additional_information in self.dims]

        # convert the list to dict with keys as the names of the dimensions.
        self.dims = {d.__class__.__name__: d for d in self.dims}
        # We need to know the index of the goal variable that is true.
        for name, _dim in self.dims.items():
            self.encoder.extend(_dim.encodings)
        
        # Create the solver.
        self.solver = Solver(ctx=self.encoder.ctx)
        self.solver.add(self.encoder.assertions)

        # Logged messages.
        self.log_msg = []

    def __len__(self) -> list:
        return [(d.name, len(d)) for d in self.dims]
    
    @property
    def ctx(self):
        return self.encoder.ctx
        
    def reset(self):
        self.solver = Solver(ctx=self.encoder.ctx)
        self.solver.add(self.encoder.assertions)
        self.log_msg.append('The solver has been reset.')

    def extract_plan(self):
        """!
        This function should update the plan with its behaviour and any extra information 
        extracted from the model.
        """
        model = self.solver.model()
        makespan_optimal_cost_bound = self.dims[MakespanOptimalCostBound.__name__]
        extracted_plan_length = makespan_optimal_cost_bound.discretize(makespan_optimal_cost_bound.value(model))
        plan = self.encoder.extract_plan(model, extracted_plan_length)
        # We need to extract the behaviour from the model.
        behaviour = self.infer_behaviour(model)
        # Update the plan with its behaviour.
        setattr(plan, "behaviour", behaviour)
        # Update its id.
        setattr(plan, "id", len(self._plans)+1)
        # Run validation if enabled.
        if self.run_plan_validation: is_plan_valid = plan.validate()
        else: setattr(plan, "isvalid", True), setattr(plan, "reason", 'Validation skipped')
        
        behaviour_str = str(behaviour)
        if not behaviour_str in self._behaviour_frequency: 
            self._behaviour_frequency[behaviour_str] = 0
        self._behaviour_frequency[behaviour_str] += 1
        self._plans.append(plan)

        if not is_plan_valid:
            self.log_msg.append(f'Plan {plan.id} is invalid. Reason: {plan.reason}')
            return None
        return plan

    def is_satisfiable(self, assumption=[], timeout=None, memorylimit=None) -> bool:
        if timeout is not None: 
            self.solver.set('timeout', timeout)
        
        if memorylimit is not None:
            self.solver.set('max_memory', memorylimit)
            
        is_formula_satisfiable = None
        try:
            is_formula_satisfiable = self.solver.check(assumption) == sat
        except Exception as e:
            is_formula_satisfiable = False
            self.log_msg.append(f'An error occured while checking the satisfiability of the formula: {e}')
        finally:
            assert is_formula_satisfiable is not None, 'The satisfiability of the formula is not determined.'
            return is_formula_satisfiable
    
    def infer_behaviour(self, model):
        behaviour_vars = []
        for dimname, dim in self.dims.items():
            behaviour_vars.append(dim.behaviour_expression(model))
        return z3.And(behaviour_vars)

    def plan_behaviour(self, plan:SequentialPlan, i=0):
        """!
        Add the plan to the behaviour space and return a its number in the behaviour space besides
        its behaviour.
        """
        assert isinstance(plan, SequentialPlan), 'The plan is not of type SequentialPlan.'
        # Get the plan's behaviour before returning its number.
        _actions = self.encoder.convert(plan)
        _tmp_assertions = []
        _tmp_assertions.extend([a == z3.BoolVal(True, ctx=self.encoder.ctx) for a in _actions])
        for _t in range(len(plan.actions), len(self.encoder)):
            _tmp_assertions.extend([a == z3.BoolVal(False, ctx=self.encoder.ctx) for a in self.encoder.get_actions_vars(_t)])
        satres = self.solver.check(_tmp_assertions) == sat
        if not satres:
            self.log_msg.append(f'The behaviour space is not satisfiable after appending plan {i}')
            return None
        self.log_msg.append(f'Plan {i} has been added to the behaviour space.')
        return self.extract_plan()
    
    def compute_behaviour_count(self):
        return len(self._behaviour_frequency.keys())
    
    def compute_dimensions_count(self):
        retdetails = defaultdict(dict)
        for dim, dimsize in len(self):
            retdetails[dim] = dimsize
        return retdetails
    
    def logs(self):
        return self.log_msg
    