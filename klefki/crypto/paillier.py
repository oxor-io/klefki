from math import gcd
from abc import ABCMeta
from random import randint
from klefki.types.algebra.utils import randfield
from klefki.types.algebra.meta import field
from klefki.numbers import lcm
from functools import partial
import random


def L(x, n):
    return (x - 1) // n


class Paillier():

    def __init__(self, P, Q):
        assert gcd(P * Q, (P - 1) * (Q - 1)) == 1

        N = P * Q
        Lam = lcm(P - 1, Q - 1)

        F = field(N)
        DF = field(N**2)
        G = randfield(DF)

        M = ~F(L(pow(G, Lam).value, N))

        self.privkey = (Lam, M)
        self.pubkey = (N, G)


    @classmethod
    def encrypt(cls, m, pub):
        N, G = pub

        if hasattr(m, "value"):
            m = m.value

        r = G.functor(random.randint(0, N))
        return G**m * r**N


    @classmethod
    def decrypt(cls, c, priv, pub):
        Lam, M = priv
        N, G = pub

        F = M.functor
        return F(L((c ** Lam).value, N)) * M

    def E(self, m, pub=None):
        return self.encrypt(m, pub or self.pubkey)


    def D(self, c, priv=None, pub=None):
        return self.decrypt(c, priv or self.privkey, pub or self.pubkey)


    def test(self):
        m = random.randint(0, self.N)
        assert m == self.D(self.E(m)).value
        return self
