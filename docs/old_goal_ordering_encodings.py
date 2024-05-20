# subgoals_encodings = []
        # subgoals_encodings.extend(self.encoder_function[encoder.name](encoder, formulalength))
                
        # _varslist = list(self._sgo_vars)
        # # We need to define uninterepted function for ordering and then use it to encode the ordering.
        # uf_gt = z3.Function('GoalPredicateOrderingFn', z3.IntSort(), z3.IntSort(), z3.IntSort())  # uf_gt(a, b) represents a > b
        # for i, sgoi in enumerate(_varslist):
        #     for j, sgoj in enumerate(_varslist[i+1:]):
        #         subgoals_encodings.append((sgoi >= sgoj) == (uf_gt(sgoi, sgoj) == 1))
        #         subgoals_encodings.append((sgoi < sgoj)  == (uf_gt(sgoi, sgoj) == 0))
                
        #         # now create a variable to hold this ordering.
        #         ordering_var = z3.Int(f'goal-predicate-ordering-{str(sgoi)}>{str(sgoj)}')
        #         self.sgo_ordering_variables.append(ordering_var)
        #         subgoals_encodings.append(ordering_var == uf_gt(sgoi, sgoj))

        # self.discrete_vars.extend(self.sgo_ordering_variables)

        # return subgoals_encodings

        # self.goal_predicates_bitvector = None
        # self.goal_predicates_vectorlen = None

        # self.goal_predicates_vectorlen = len(_varslist)

        # Second encoding using the permutations.
        # assert len(_varslist) <= 8, "We cannot handle more than 10 goal predicates due to memory limitation."

        # self.goal_predicates_bitvector = z3.Int('goal-predicates-vector')
        # self.discrete_vars.append(self.goal_predicates_bitvector)
        # # all_possible_orders = []
        # self.maximum_possible_permutation_values = 1000
        # for i, sequence in enumerate(permutations(_varslist)):
        #     # if i > self.maximum_possible_permutation_values: 
        #     #     break
        #     order_encoding = []
        #     for j in range(0, len(sequence)-1):
        #         order_encoding.append(sequence[j] <= sequence[j+1])
        #     anded_order_encoding = z3.And(order_encoding)
        #     subgoals_encodings.append(anded_order_encoding == (self.goal_predicates_bitvector == z3.IntVal(i)))
        #     # all_possible_orders.append(z3.Not(anded_order_encoding))
        # # subgoals_encodings.append(z3.And(all_possible_orders) == (self.goal_predicates_bitvector == z3.IntVal(i+1)))
        # subgoals_encodings.append(self.goal_predicates_bitvector >= z3.IntVal(0))
        # subgoals_encodings.append(self.goal_predicates_bitvector < z3.IntVal(i+2))
        # return subgoals_encodings
        
        ## First encoding we had.

        # Encode the subgoals ordering into a bitvector to infer the ordering without the need to sort them outside the solver.
        # Trying the bit vector encoding.
        # cmpsvars = []
        # cmpsvarsstr = []
        # for i, sgo1 in enumerate(_varslist):
        #     for sgo2 in _varslist[i+1:]:
        #         _vectname = f'goal-predicate-cmp-{len(cmpsvars)+1}'
        #         cmp = BitVec(_vectname, self.goal_predicates_vectorlen)
        #         subgoals_encodings.append(cmp == z3.If(sgo1 <= sgo2, z3.BitVecVal(1, self.goal_predicates_vectorlen), z3.BitVecVal(0, self.goal_predicates_vectorlen)))
        #         cmpsvars.append(cmp)
        #         cmpsvarsstr.append(f'cmpsvars[{(len(cmpsvars)-1)}] << {(len(cmpsvars)-1)}')
        # cmpsvarsstr = ' | '.join(cmpsvarsstr)
        # self.goal_predicates_bitvector = z3.BitVec('goal-predicates-vector', self.goal_predicates_vectorlen)
        # self.discrete_vars.append(self.goal_predicates_bitvector)
        # if cmpsvarsstr == '':
        #     subgoals_encodings.append(self.goal_predicates_bitvector == z3.BitVecVal(0, self.goal_predicates_vectorlen))
        # else:
        #     subgoals_encodings.append(self.goal_predicates_bitvector == (z3.BitVecVal(0, self.goal_predicates_vectorlen) | eval(cmpsvarsstr) ))

        # # Trying z3 bit blasting tactics.
        # _g = z3.Goal()
        # _g.add(subgoals_encodings)
        # return [z3.Then('simplify', 'bit-blast', 'tseitin-cnf')(_g)[0]]
        # return subgoals_encodings
