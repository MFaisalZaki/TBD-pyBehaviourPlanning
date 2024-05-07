# pyForbidBehaviourIterative
TODO

# Build

```
# mkdir -p bplanning/v-env && cd bplanning/v-env && python3 -m venv . && source bin/activate && cd ..
mkdir bplanning
git clone https://github.com/MFaisalZaki/pyBehaviourSortsSuite.git
cd pyBehaviourSortsSuite && python3 setup.py install --user && cd ..
git clone https://github.com/MFaisalZaki/pyForbidBehaviourIterative.git
cd pyForbidBehaviourIterative && python3 setup.py install --user && cd ..
```

# How to use
## 1. CLI
```
usage: bplanningcli [-h] [-k K] [-q Q] [--add-goal-ordering] [--add-resource-count] [--resource-file RESOURCE_FILE] [--add-makespan] [--disable-action-check] [--dump-dir DUMP_DIR] plannercfg domain problem.pddl
```

- `k`: required number of plans to generate.
- `q`: quality bound factor.
- `--add-goal-ordering`: flag to add goal predicate ordering dimension.
- `--add-resource-count`: flag to add resource count dimension.
- `--resource-file`: file containing the additional information for the resource utilisation (syntax can be found in [BSS](https://github.com/MFaisalZaki/pyBehaviourSortsSuite.git)).
- `--add-makespan`: flag to add the makespan optimal dimension.
- `--disable-action-check`: flag to allow steps with no actions.
- `plannercfg`: planner configuration json file with the following structure
```
planner_params = {
  'base-planner-cfg': {
    "base-planner": PlanningType.SYMK,
    "solver-timeout-ms": 600000,
    "solver-memorylimit-mb": 16000,
    "k": 10 # This is optional if not passed then the planner will keep looking for all available behaviours.
  },
  'bspace-cfg': {
    'dims': dims,
    "quality-bound-factor": 1.1,
    "upper-bound": 100,
    "disable-action-check": False,
    "run-plan-validation": True
  }
}
```

## 2. API interface
```
from unified_planning.io import PDDLReader
from bss.shortcuts import GoalPredicatesOrdering, MakespanOptimalCostBound, ResourceCount
from fbi.shortcuts import *

# 1. Construct the planner's parameters:
# - define the behaviour space's dimensions 
dims  = []
dims += [(GoalPredicatesOrdering, None)]
dims += [(MakespanOptimalCostBound, {"disable_action_check": False})]
dims += [(ResourceCount, <Path to resource utilisation file>)]

planner_params = {
  'base-planner-cfg': {
    "base-planner": PlanningType.SYMK,
    "solver-timeout-ms": 600000,
    "solver-memorylimit-mb": 16000,
    "k": 10 # This is optional if not passed then the planner will keep looking for all available behaviours.
  },
  'bspace-cfg': {
    'dims': dims,
    "quality-bound-factor": 1.1,
    "upper-bound": 100,
    "disable-action-check": False,
    "run-plan-validation": True
  }
}

domain  = <path to domain file>
problem = <path to instance file>

task = PDDLReader().parse_problem(domain, problem)

fbi = ForbidBehaviourIterative(task, planner_params['bspace-cfg'], planner_params['base-planner-cfg'])
if 'k' in planner_params['base-planner-cfg']: fbi.plan(planner_params['base-planner-cfg']['k'])
else: fbi.plan()

```

## 3. UP Wrapper
```
from unified_planning.io import PDDLReader
from unified_planning.shortcuts import OneshotPlanner
from bss.shortcuts import GoalPredicatesOrdering, MakespanOptimalCostBound, ResourceCount
from fbi.shortcuts import *

# ... define the planner_params
# ... define the planning task

with OneshotPlanner(name='FBIPlanner',  params=planner_params) as planner:
  result = planner.solve(task)

```
