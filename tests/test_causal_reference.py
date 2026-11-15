"""A mathematical regression check of the production shifted-supervision contract."""
import math
import unittest
from dream_core.contracts import predictor_mask


def causal_loss(parameter, coefficient, mask):
    # A minimal causal shared-parameter network, not an open-weight LLM.
    x=[.2,.4,-.1,.5]
    y=[0,1,0,1]
    h=[parameter*sum(x[:i+1])+coefficient*int(mask[i]) for i in range(len(x))]
    return sum(math.log(math.exp(h[i])+math.exp(-h[i]))-(h[i] if y[i+1]==0 else -h[i])
               for i in range(len(x)-1))/(len(x)-1)


def gradient(coefficient,mask):
    e=1e-5
    return (causal_loss(.7+e,coefficient,mask)-causal_loss(.7-e,coefficient,mask))/(2*e)


class CausalReferenceTests(unittest.TestCase):
    def test_legacy_unscored_position_has_zero_influence(self):
        mask=[False,False,False,True]
        self.assertEqual(causal_loss(.7,0,mask),causal_loss(.7,.2,mask))
        self.assertEqual(gradient(0,mask),gradient(.2,mask))

    def test_actual_mask_changes_loss_and_gradient(self):
        mask=predictor_mask([-100,1,0,1])
        self.assertNotEqual(causal_loss(.7,0,mask),causal_loss(.7,.2,mask))
        self.assertGreater(abs(gradient(0,mask)-gradient(.2,mask)),1e-4)


if __name__=="__main__": unittest.main()
