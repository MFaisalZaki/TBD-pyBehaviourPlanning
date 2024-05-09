# Behaviour Sorts Suite (BSS)
BSS contains three components:
- Behaviour Space
- Behaviour Features Library
- Behaviour Count

# Constructing a behaviour space
It is a discretisation for the solution space based on a set of features the domain modeller selects. In this package, we use planning-as-SMT to generate a plan and infer its behaviour. To construct a behaviour space, we define which features to include. Currently, we are providing three features:
- [ ] MakespanOptimalCostBound
- [ ] GoalPredicatesOrdering
- [ ] ResourceCount
However, those features can be easily extended by the user.

```
from unified_planning.io import PDDLReader
from behaviour_planning.over_domain_models.smt.shortcuts import BehaviourSpace, GoalPredicatesOrdering, MakespanOptimalCostBound, ResourceCount

resources_file = <this file contains the required information for resources dimension,
check the following section for syntax>

dimensions  = []
# A feature is a 2-tuple element, where the first is the dimension class
# and the second is additional information required by the dimension.
dimensions += [(GoalPredicatesOrdering, {})]
dimensions += [(ResourceCount, resources_file)]
dimensions += [(MakespanOptimalCostBound, {})]

bspace_cfg = {'dims': dimensions}

domain  = <problem pddl domain file>
problem = <problem pddl instance file>

task = PDDLReader().parse_problem(domain, problem)

bspace = BehaviourSpace(task, bspace_cfg)

```
Now, we have a ready-to-use behaviour space. You could enable plan validation by appending `'run-plan-validation':True` to `bspace_cfg`. 
Since behaviour spaces use planning-as-SMT, you can control the plan length by appending `'upper-bound: N` to `bspace_cfg` where `N` is the formula length. 

# Using behaviour spaces
## 1. Plan behaviour
You can use behaviour space to create a plan and infer its behaviour:
```
assert bspace.is_satisfiable(), 'The behaviour space is not satisfiable.'
plan = bspace.extract_plan()
print(plan.behaviour)
```
## 2. Behaviour count
Behaviour spaces can count the behaviours presented in a given plan set.
```
from behaviour_planning.over_domain_models.smt.shortcuts import BehaviourCount
planlist = [.. Set of plans read from sas plan files  ..]
bspace = BehaviourCount(domain, problem, bspace_cfg, planlist)
behaviour_count = bspace.count()
```

## How to pass resource utilistation informaion?
BSpace expects a `.pddl` file with the following structure:
```
(:resource NAME MAX MIN STEP)
```

Here is an example for the rover problem where it pass both numeric and classic information to the model:
```
(:resource rover0 100 0 5)
(:resource energy(rover0) 50 0 2)
```
