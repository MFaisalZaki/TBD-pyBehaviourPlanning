
from copy import deepcopy
from collections import defaultdict

# from unified_planning.shortcuts import *
from unified_planning.shortcuts import get_environment
from unified_planning.shortcuts import Compiler, CompilationKind
from unified_planning.shortcuts import Effect, EffectKind, FNode

import z3

from unified_planning.plans import SequentialPlan
from unified_planning.plans import ActionInstance

from behaviour_planning_smt.bss.behaviour_space.formula_encoders.utilities import str_repr

from behaviour_planning_smt.bss.behaviour_space.formula_encoders.smt_sequential_plan import SMTSequentialPlan

class EncoderGrounded:
    def __init__(self, name, task):
        self.task = task # The UP problem
        self.name = name
        self.ctx = z3.Context() # The context where we will store the problem

        self.compilation_results = self._ground() # store the compilation results
        self.grounding_results   = self.compilation_results[-1] # store the grounded UP results
        self.ground_problem      = self.grounding_results.problem  # The grounded UP problem

        # The main idea here is that we have lists representing
        # the layers (steps) containing the respective variables

        # this is a mapping from the UP ground actions to z3 and back
        self.z3_actions_to_up = dict() # multiple z3 vars point to one grounded fluent
        self.up_actions_to_z3 = defaultdict(list)
        
        # mapping from up fluent to Z3 var
        self.up_fluent_to_z3 = defaultdict(list) 

        # frame index, indexing what actions can modify which fluent
        self.frame_add = defaultdict(list)
        self.frame_del = defaultdict(list)
        self.frame_num = defaultdict(list)

        # Store the "raw" formula that we will later instantiate
        self.formula  = defaultdict(list) 

        # Store the length of the formula
        self.formula_length = 0

        # Store action to number map.
        self.action_name_to_number = defaultdict(dict)

        # Store all goal states.
        self.goal_states = []

        # Store all assertions.
        self.assertions = []

    def __iter__(self):
        return iter(self.ground_problem.actions)
    
    def __len__(self):
        return self.formula_length

    def get_action_var(self, name, t):
        """!
        Function used to recover the plan: given the var name and step, 
        return the z3 var
        """
        return self.up_actions_to_z3[name][t]

    def get_all_action_vars(self, name):
        """!
        Function used to recover the plan: given the var name, 
        return all the z3 vars
        """
        return self.up_actions_to_z3[name]

    def _ground(self):
        """! Removes quantifiers and grounds the problem using a UP grounder """
        get_environment().credits_stream  = None
        get_environment().error_used_name = False
        
        with Compiler(problem_kind = self.task.kind, 
                      compilation_kind = CompilationKind.QUANTIFIERS_REMOVING) as quantifiers_remover:
            qr_result  = quantifiers_remover.compile(self.task, CompilationKind.QUANTIFIERS_REMOVING)

        with Compiler(problem_kind = qr_result.problem.kind, 
                      compilation_kind = CompilationKind.GROUNDING) as grounder:
            gr_result = grounder.compile(qr_result.problem, CompilationKind.GROUNDING)
        return (qr_result, gr_result)
        
    def _populate_modifiers(self):
        """
        Populate an index on who can modify who on the grounded actions 
        """
        for action in self.ground_problem.actions:
            str_action = str_repr(action)
            for effect in action.effects:
               var_modified = str_repr(effect.fluent)
               if effect.value.is_true(): # boolean effect
                   self.frame_add[var_modified].append(str_action)
               elif effect.value.is_false():
                   self.frame_del[var_modified].append(str_action)
               else: # is a numeric or complex expression
                   self.frame_num[var_modified].append(str_action)

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

    def base_encode(self):
        """!
        Builds the encoding. Populates the formula dictionary, where all the "raw" formulas are stored
        @return None
        """
        # create vars for first transition
        self.create_variables(0)
        self.create_variables(1)
        self._populate_modifiers() # do indices

        self.formula['initial'] = z3.And(self.encode_initial_state())  # Encode initial state axioms
        self.formula['goal']    = z3.And(self.encode_goal_state(0))  # Encode goal state axioms
        self.formula['actions'] = z3.And(self.encode_actions(0))  # Encode universal axioms
        self.formula['frame']   = z3.And(self.encode_frame(0))  # Encode explanatory frame axioms
        self.formula['sem']     = z3.And(self.encode_execution_semantics())  # Encode execution semantics (lin/par)

    def encode_execution_semantics(self):
        """!
        Encodes execution semantics as specified by modifier class.

        @return axioms that specify execution semantics.
        """
        return z3.PbLe([(var, 1) for var in list(map(lambda x: x[0], self.up_actions_to_z3.values()))], 1)

    def create_variables(self, t):
        """!
        Creates state variables needed in the encoding for step t.
        """
        # increment the formula lenght
        self.formula_length += 1

        # for actions
        for grounded_action in self.ground_problem.actions:
            key   = str_repr(grounded_action)
            keyt  = str_repr(grounded_action, t)
            act_var = z3.Bool(keyt, ctx=self.ctx)
            self.up_actions_to_z3[key].append(act_var)
            self.z3_actions_to_up[act_var] = key

        # for fluents
        grounded_up_fluents = [f for f, _ in self.ground_problem.initial_values.items()]
        for grounded_fluent in grounded_up_fluents:
            key  = str_repr(grounded_fluent)
            keyt = str_repr(grounded_fluent, t)
            if grounded_fluent.type.is_real_type():
                self.up_fluent_to_z3[key].append(z3.Real(keyt, ctx=self.ctx))
            elif grounded_fluent.type.is_bool_type():
                self.up_fluent_to_z3[key].append(z3.Bool(keyt, ctx=self.ctx))
            else:
                raise TypeError

    def encode_initial_state(self):
        """!
        Encodes formula defining initial state
        @return initial: Z3 formula asserting initial state
        """
        t = 0
        initial = []
        for FNode, initial_value in self.task.initial_values.items():
            fluent = self._expr_to_z3(FNode, t)
            value  = self._expr_to_z3(initial_value, t)
            initial.append(fluent == value)
        return initial

    def encode_goal_state(self, t):
        """!
        Encodes formula defining goal state
        @return goal: Z3 formula asserting propositional and numeric subgoals
        """
        goal = []
        for goal_pred in self.task.goals:
            goal.append(self._expr_to_z3(goal_pred, t + 1))
        return goal

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

    def encode_frame(self, t):
        """!
        Encodes the explanatory frame axiom

        basically for each fluent, to change in value it means
        that some action that can make it change has been executed
        f(x,y,z, t) != f(x,y,z, t+1) -> a \/ b \/ c
        """
        frame = [] # the whole frame

        # for each grounded fluent, we say its different from t to t + 1
        grounded_up_fluents = [f for f, _ in self.ground_problem.initial_values.items()]
        for grounded_fluent in grounded_up_fluents:
            key    = str_repr(grounded_fluent)
            var_t  = self.up_fluent_to_z3[key][t]
            var_t1 = self.up_fluent_to_z3[key][t + 1]

            # for each possible modification
            or_actions = []
            or_actions.extend(self.frame_add[key])
            or_actions.extend(self.frame_del[key])
            or_actions.extend(self.frame_num[key])

            # simplify the list in case its empty
            if len(or_actions) == 0:
                who_can_change_fluent = z3.BoolVal(False, ctx=self.ctx)
            else:
                who_can_change_fluent = z3.Or([self.up_actions_to_z3[x][t] for x in or_actions])

            frame.append(z3.Implies(var_t != var_t1, who_can_change_fluent))
        return frame

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

    def convert(self, plan):
        return [self.up_actions_to_z3[self._up_actionname_to_z3(a)][t] for t, a in enumerate(plan.actions)]

    def extend(self, asserstions_list):
        self.assertions.extend(asserstions_list)
    
    def get_actions_vars(self, step):
        return list(map(lambda x: x[step], self.up_actions_to_z3.values()))

    def _up_actionname_to_z3(self, action_name):
        return f'{(str(action_name).replace("(","_").replace(")","").replace(", ", "_"))}'
    
    def _expr_to_z3(self, expr, t, c=None):
        """
        Traverses a tree expression in-order and converts it to a Z3 expression.
        expr: The tree expression node. (Can be a value, variable name, or operator)
        t: The timestep for the Fluents to be considered 
        c: A context manager, as we need to take into account parameters from actions, fluents, etc ...
        Returns A Z3 expression or Z3 value.
        """
        if isinstance(expr, int): # A python Integer
            return z3.IntVal(expr, ctx=self.ctx)
        elif isinstance(expr, bool): # A python Boolean
            return z3.BoolVal(expr, ctx=self.ctx)

        elif isinstance(expr, Effect): # A UP Effect
            eff = None
            if expr.kind == EffectKind.ASSIGN:
                eff = self._expr_to_z3(expr.fluent, t + 1, c) == self._expr_to_z3(expr.value, t, c)
            if expr.kind == EffectKind.DECREASE:
                eff = self._expr_to_z3(expr.fluent, t + 1, c) == self._expr_to_z3(expr.fluent, t, c) - self._expr_to_z3(expr.value, t, c)
            if expr.kind == EffectKind.INCREASE:
                eff = self._expr_to_z3(expr.fluent, t + 1, c) == self._expr_to_z3(expr.fluent, t, c) + self._expr_to_z3(expr.value, t, c)
            if expr.is_conditional():
                return z3.Implies(self._expr_to_z3(expr.condition, t, c) , eff)
            else:
                return eff

        elif isinstance(expr, FNode): # A UP FNode ( can be anything really )
            if expr.is_object_exp(): # A UP object
                raise ValueError(f"{expr} should not be evaluated")
            elif expr.is_constant(): # A UP constant
                return expr.constant_value()
            elif expr.is_or():  # A UP or
                return z3.Or([self._expr_to_z3(x, t, c) for x in expr.args])
            elif expr.is_and():  # A UP and
                return z3.And([self._expr_to_z3(x, t, c) for x in expr.args])
            elif expr.is_fluent_exp(): # A UP fluent
                return self.up_fluent_to_z3[str_repr(expr)][t]
            elif expr.is_parameter_exp():
                raise ValueError(f"{expr} should not be evaluated")
            elif expr.is_lt():
                return self._expr_to_z3(expr.args[0], t, c) < self._expr_to_z3(expr.args[1], t, c)
            elif expr.is_le():
                return self._expr_to_z3(expr.args[0], t, c) <= self._expr_to_z3(expr.args[1], t, c)
            elif expr.is_times():
                return self._expr_to_z3(expr.args[0], t, c) * self._expr_to_z3(expr.args[1], t, c)
            elif expr.is_plus():
                return z3.Sum([self._expr_to_z3(x, t, c) for x in expr.args])
            elif expr.is_minus():
                return self._expr_to_z3(expr.args[0], t, c) - self._expr_to_z3(expr.args[1], t, c)
            elif expr.is_not():
                return z3.Not(self._expr_to_z3(expr.args[0], t, c))
            else:
                raise TypeError(f"Unsupported expression: {expr} of type {type(expr)}")
        else:
            raise TypeError(f"Unsupported expression: {expr} of type {type(expr)}")

class EncoderSequential(EncoderGrounded):
    """
    Class that encodes a problem to a classical sequential encoding to SMT
    """
    def __init__(self, task):
        super().__init__("seq", task)