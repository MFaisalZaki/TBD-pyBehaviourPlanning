from unified_planning.io import PDDLReader

from behaviour_planning.over_domain_models.smt.bss.behaviour_space.space_encoders.basic import BehaviourSpace

class BehaviourCount:
    def __init__(self, domain, problem, bspace_cfg, planlist):
        planningtask = PDDLReader().parse_problem(domain, problem)
        
        # remove the lines with ;
        bspace_cfg['upper-bound'] = max(set([len(plan.split('\n')) for plan in planlist]))
        
        self.bspace = BehaviourSpace(planningtask, bspace_cfg)
        planlist = [PDDLReader().parse_plan_string(planningtask, plan) for plan in planlist]
        
        for i, plan in enumerate(planlist):
            ret = self.bspace.plan_behaviour(plan, i)
            if ret is None: self.bspace.log_msg.append(f'Plan {i} is not satisfiable.')

    def count(self):
        return self.bspace.compute_behaviour_count()
    
    def logs(self):
        return self.bspace.log_msg
