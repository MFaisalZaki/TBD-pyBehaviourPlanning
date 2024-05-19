
from copy import deepcopy
from collections import defaultdict

import z3

from unified_planning.plans import SequentialPlan
from unified_planning.plans import ActionInstance

from pypmt.encoders.basic import EncoderSequential
from pypmt.encoders.utilities import str_repr

from behaviour_planning.over_domain_models.smt.bss.behaviour_space.formula_encoders.smt_sequential_plan import SMTSequentialPlan

# append some extra functions to the EncoderSequential.

def encode_step(self, t):
    """!
    Builds and returns the formulas for a single transition step (from t to t+1).
    @param t: timestep where the goal is true
    @return encoded_formula: A dict with the different parts of the formula encoded
    """
    if t == 0:
        self.base_encode()
        return deepcopy(self.formula)
    
    self.create_variables(t+1) # we create another layer

    list_substitutions = [] # list of pairs (from,to)
    for key in self.up_actions_to_z3.keys():
        list_substitutions.append(
            (self.up_actions_to_z3[key][0],
                self.up_actions_to_z3[key][t]))
    for key in self.up_fluent_to_z3.keys():
        list_substitutions.append(
            (self.up_fluent_to_z3[key][0],
                self.up_fluent_to_z3[key][t]))
        list_substitutions.append(
            (self.up_fluent_to_z3[key][1],
                self.up_fluent_to_z3[key][t + 1]))

    encoded_formula = dict()
    encoded_formula['initial'] = self.formula['initial'] # TODO not needed?
    encoded_formula['goal']    = z3.substitute(self.formula['goal'], list_substitutions)
    encoded_formula['actions'] = z3.substitute(self.formula['actions'], list_substitutions)
    encoded_formula['frame']   = z3.substitute(self.formula['frame'], list_substitutions)
    encoded_formula['sem']     = z3.substitute(self.formula['sem'], list_substitutions)
    return encoded_formula

def encode(self, formula_length):
    """!
    This method encodes a formula into a list of assertions.

    It iterates over the formula length, encoding each step into a formula and appending the 'goal' state to the goal_states list.
    If it's the first step, it also appends the 'initial' state to the assertions list.
    It then removes 'goal', 'initial', 'sem', and 'objective' (if present) from the formula.
    Any remaining items in the formula are appended to the assertions list if they are not None.

    After encoding the formula, it adds the execution semantics to the assertions list.
    It does this by mapping each action in up_actions_to_z3 to its corresponding value at time t.
    If it's the last step of the formula, the number of actions is set to 0, otherwise it's set to 1.
    It then creates a PbEq (pseudo-boolean equality) constraint with the actions and the number of actions, and appends it to the assertions list.

    Finally, it encodes the possible goal states into a PbGe (pseudo-boolean greater or equal) constraint and appends it to the assertions list.

    Parameters:
    formula_length (int): The length of the formula to encode.

    Returns:
    list: The list of assertions resulting from the encoding.
    """
    for t in range(0, formula_length):
        formula = self.encode_step(t)
        self.goal_states.append(formula['goal'])
        if t == 0: self.assertions.append(formula['initial'])
        del formula['goal']
        del formula['initial']
        del formula['sem']
        if 'objective' in formula: del formula['objective']
        for k, v in formula.items():
            if v is not None: self.assertions.append(v)
    
    # Add the extection sematics.
    for t in range(0, self.formula_length):
        actions = list(map(lambda x: x[t], self.up_actions_to_z3.values()))
        # Disable the actions in the last step of the formula.
        execution_semantics = None
        if t == self.formula_length-1:
            execution_semantics = z3.PbEq([(var, 1) for var in actions], 0, ctx=self.ctx) 
        else:
            execution_semantics = z3.PbLe([(var, 1) for var in actions], 1)
        self.assertions.append(execution_semantics)
    
    # Encode possible goal states.
    self.assertions.append(z3.PbGe([(g,1) for g in self.goal_states], 1))
    return self.assertions

def get_actions_vars(self, step):
    return list(map(lambda x: x[step], self.up_actions_to_z3.values()))

def extend(self, asserstions_list):
    self.assertions.extend(asserstions_list)

def convert(self, plan):
    return [self.up_actions_to_z3[self._up_actionname_to_z3(a)][t] for t, a in enumerate(plan.actions)]

def _up_actionname_to_z3(self, action_name):
    return f'{(str(action_name).replace("(","_").replace(")","").replace(", ", "_"))}'

def extract_plan(self, model, horizon):
    plan = SequentialPlan([])
    selected_actions_vars = []
    actions_sequence = []
    if not model: return plan
    ## linearize partial-order plan
    for t in range(0, horizon+1):
        for action in self:
            if z3.is_true(model[self.up_actions_to_z3[action.name][t]]):
                plan.actions.append(ActionInstance(action))
                selected_actions_vars.append(self.up_actions_to_z3[action.name][t])
                actions_sequence.append(self.action_name_to_number[action.name])
                break

    for compilation_r in reversed(self.compilation_results):
        plan = plan.replace_action_instances(compilation_r.map_back_action_instance)

    return SMTSequentialPlan(plan, self.task, selected_actions_vars, '-'.join(actions_sequence))

def encode_actions(self, t):
    """!
    Encodes the Actions
    @return actions: list of Z3 formulas asserting the actions

    The encoding is the classic
    a -> Pre
    a -> Eff
    """
    actions = []
    for grounded_action in self.ground_problem.actions:
        key = str_repr(grounded_action)
        action_var = self.up_actions_to_z3[key][t]

        # translate the action precondition
        action_pre = []
        for pre in grounded_action.preconditions:
            action_pre.append(self._expr_to_z3(pre, t))
        # translate the action effect
        action_eff = []
        for eff in grounded_action.effects:
            action_eff.append(self._expr_to_z3(eff, t))

        # the proper encoding
        action_pre = z3.And(action_pre) if len(action_pre) > 0 else z3.BoolVal(True, ctx=self.ctx)
        actions.append(z3.Implies(action_var, action_pre, ctx=self.ctx))
        action_eff = z3.And(action_eff) if len(action_eff) > 0 else z3.BoolVal(True, ctx=self.ctx)
        actions.append(z3.Implies(action_var, action_eff, ctx=self.ctx))

        # encode this action to a number
        self.action_name_to_number[key] = str(len(self.action_name_to_number)+1)
    return z3.And(actions)

def encode_execution_semantics(self):
    return z3.PbLe([(var, 1) for var in list(map(lambda x: x[0], self.up_actions_to_z3.values()))], 1)


# Update the encoder apis.
# Store action to number map.
setattr(EncoderSequential, 'action_name_to_number', defaultdict(dict))
# Store all goal states.
setattr(EncoderSequential, 'goal_states', [])
# Store all assertions.
setattr(EncoderSequential, 'assertions', [])
setattr(EncoderSequential, 'encode', encode)
setattr(EncoderSequential, 'encode_step', encode_step)
setattr(EncoderSequential, 'get_actions_vars', get_actions_vars)
setattr(EncoderSequential, 'extend', extend)
setattr(EncoderSequential, 'convert', convert)
setattr(EncoderSequential, '_up_actionname_to_z3', _up_actionname_to_z3)
setattr(EncoderSequential, 'extract_plan', extract_plan)
setattr(EncoderSequential, 'encode_actions', encode_actions)
setattr(EncoderSequential, 'encode_execution_semantics', encode_execution_semantics)