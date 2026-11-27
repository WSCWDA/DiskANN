import unittest
import numpy as np
from execution_window import *
from run_execution_window import plan,CASES
class Test(unittest.TestCase):
    def test_oracle(self):
        s=[{1},{2},{1},{2},{3}]
        o=reorder(list(range(5)),lambda g:oracle_score(s,g),4,2)
        self.assertEqual(o,[0,2,1,3,4]);self.assertEqual(window_overlap(o,s,4,2),2)
    def test_vector(self):
        x=np.array([[0],[10],[1],[11]])
        self.assertEqual(reorder(list(range(4)),lambda g:vector_score(x,g),4,2),[0,2,1,3])
    def test_random(self):
        a=list(range(513));b=random_order(a);check_membership(a,b);self.assertEqual(b,random_order(a))
    def test_invalid(self):
        with self.assertRaises(ValueError):check_membership([0,1,2,3],[2,1,0,3],2)
        with self.assertRaises(ValueError):reorder([0],lambda g:[[float('nan')]])
    def test_tail(self):
        a=list(range(9));b=reorder(a,lambda g:np.zeros((len(g),len(g))),4,3);self.assertEqual(a,b)
    def test_matrix(self):
        self.assertEqual(len(set(plan(3))),30);self.assertEqual(len(plan(1)),10);self.assertEqual(len(CASES),10)
if __name__=='__main__':unittest.main()
