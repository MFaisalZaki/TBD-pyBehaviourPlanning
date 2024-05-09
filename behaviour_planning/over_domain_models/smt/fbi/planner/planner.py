import sys
import math
from collections import defaultdict

from enum import Enum

from unified_planning.shortcuts import OneshotPlanner, AnytimePlanner
import unified_planning.engines.results as UPResults
import up_symk

import z3

from behaviour_planning_smt.shortcuts import BehaviourSpace, compute_behaviour_space_statistics


# Create an enum for the different types of planning
class PlanningType(Enum):
    R2E  = 1
    SMT  = 2
    SYMK = 3

class ForbidMode(Enum):
    BEHAVIOUR = 1
    PLAN      = 2

class ForbidBehaviourIterative:
    def __init__(self, task, bspace_cfg, planner_cfg):
        self.task   = task
        self.bspace = None

        self.base_planner       = planner_cfg.get('base-planner', PlanningType.SYMK)
        self.solver_timeout     = planner_cfg.get('solver-timeout-ms', 600000)
        self.solver_memorylimit = planner_cfg.get('solver-memorylimit-mb', 16000)

        self.log_msg = []
        self.diverse_plans = []
        self.diverse_plans_actions_sequence = set()

        seedplan = self.solve(task)

        if not seedplan is None:
            quality_bound_factor      = bspace_cfg.get('quality-bound-factor', 1.0)
            bspace_cfg['upper-bound'] = int(math.floor(len(seedplan.actions)*quality_bound_factor))
            assert bspace_cfg['upper-bound'] >= 1, 'The upper bound is less than or equal to zero.'

            # Construct the behaviour space
            self.bspace = BehaviourSpace(task, bspace_cfg)
            # Add seed plan to the the list of generated behaviours.
            plan = self.bspace.plan_behaviour(seedplan)
            if plan is not None: self.update(plan)
        
            # Get the same context as the behaviour space.
            self.ctx = self.bspace.ctx
        else:
            self.log_msg.append('Seed plan could not be generated.')

    def plan(self, required_plancount = sys.maxsize):
        # Try to generate plans that are diverse in terms of behaviours.
        self.core(ForbidMode.BEHAVIOUR, required_plancount)
        # If we did not get enough diverse behaviours, then try to generate plans from those behaviours.
        if (len(self.diverse_plans) < required_plancount) and (required_plancount != sys.maxsize):
            self.core(ForbidMode.PLAN, required_plancount)
        return self.diverse_plans
    
    def core(self, forbid_mode, required_plancount):

        if self.bspace is None:
            self.log_msg.append('Behaviour space could not be constructed.')
            return

        if len(self.diverse_plans) == 0:
            self.log_msg.append('Seed plan invalidated the behaviour space.')

        behaviours_list = []
        plans_list      = []

        for plan in self.diverse_plans:
            behaviours_list.append(plan.behaviour)
            plans_list.append(z3.Not(z3.And(plan._z3_plan), ctx=self.ctx))

        assumptions = []
        assumptions.append(z3.Not(z3.Or(behaviours_list), ctx=self.ctx) if forbid_mode == ForbidMode.BEHAVIOUR else z3.Or(behaviours_list))
        assumptions.extend(plans_list)
        while self.bspace.is_satisfiable(assumptions, self.solver_timeout, self.solver_memorylimit) and (len(self.diverse_plans) < required_plancount):
            # Extract plan from the behaviour space.
            plan = self.bspace.extract_plan()
            # Update the diverse plan list and check that we don't have repeated plans.
            self.update(plan)
            # Append the behaviour to the list of behaviours.
            if forbid_mode == ForbidMode.BEHAVIOUR:
                behaviours_list.append(plan.behaviour)
            # Update the our assumptions.
            assumptions = []
            assumptions.append(z3.Not(z3.Or(behaviours_list), ctx=self.ctx) if forbid_mode == ForbidMode.BEHAVIOUR else z3.Or(behaviours_list))
            plans_list.append(z3.Not(z3.And(plan._z3_plan), ctx=self.ctx))
            assumptions.extend(plans_list)
            print("Found {} till now: {}".format('behaviour(s)' if forbid_mode == ForbidMode.BEHAVIOUR else 'plan(s)', len(self.diverse_plans)))

    def solve(self, task):
        if isinstance(self.base_planner, str): self.base_planner = eval(self.base_planner)
        seedplan      = None
        plannername   = 'symk-opt' #if self.base_planner == PlanningType.SYMK else 'SMTPlanner'
        plannerparams = {}

        match self.base_planner:
            case PlanningType.SYMK:
                plannerparams.update({'symk_search_time_limit': '900s'})
            # case PlanningType.R2E:
            #     plannerparams.update({'modifier': 'ModifierType.NA', 'encoder': 'EncoderType.R2E', 'upper_bound': 1000})
            # case PlanningType.SMT:
            #     plannerparams.update({'modifier': 'ModifierType.LINEAR', 'encoder': 'EncoderType.SMT', 'upper_bound': 1000})
            case _:
                raise Exception("Unknown planning type {}".format(self.base_planner))
            
        with OneshotPlanner(name=plannername,  params=plannerparams) as planner:
            result   = planner.solve(task)
            seedplan = result.plan if result.status in UPResults.POSITIVE_OUTCOMES else None
        return seedplan
    
    def update(self, plan):
        # Make sure that we did not get a repeated plan.
        if plan.actions_sequence in self.diverse_plans_actions_sequence:
            self.log_msg.append('Repeated plan generated.')
            return
        self.diverse_plans_actions_sequence.add(plan.actions_sequence)
        self.diverse_plans.append(plan)

    def logs(self):
        ret_logs = {}
        ret_logs['fbi-logs']     = self.log_msg
        ret_logs['bspace-logs']  = self.bspace.logs() if self.bspace is not None else 'bspace is None.'
        ret_logs['bspace-stats'] = compute_behaviour_space_statistics(self.diverse_plans, self.bspace)
        return ret_logs
