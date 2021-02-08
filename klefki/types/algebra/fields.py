from abc import abstractproperty
from .abstract import Field
from klefki.algorithms import extended_euclidean_algorithm
from klefki.algorithms import complex_truediv_algorithm
from klefki.algorithms import deg, poly_rounded_div


class FiniteField(Field):

    P = abstractproperty()

    def fmap(self, o):
        value = getattr(o, 'value', o)
        if isinstance(value, complex):
            return complex((value.real % self.P), (value.imag % self.P))
        return value % self.P

    def inverse(self):
        return self.__class__(self.P - self.value)

    def mod(self, a, b):
        if isinstance(a, complex):
            return complex((a.real % b), (a.imag % b))
        return a % b

    def sec_inverse(self):
        if isinstance(self.value, complex):
            return complex_truediv_algorithm(complex(1), self.value, self.__class__)

        gcd, x, y = extended_euclidean_algorithm(self.value, self.P)
        assert (self.value * x + self.P * y) == gcd
        # if gcd != 1:
        #     # Either n is 0, or p is not prime number
        #     raise ValueError(
        #         '{} has no multiplicate inverse '
        #         'modulo {}'.format(self.value, self.P)
        #     )
        return self.__class__(x % self.P)

    def op(self, g):
        if isinstance(g, int):
            g = self.functor(g)
        return self.__class__(
            self.mod(
                (self.value + g.value), self.P
            )
        )

    def sec_op(self, g):
        if isinstance(g, int):
            g = self.functor(g)
        return self.__class__(
            self.mod(
                (self.value * g.value), self.P
            )
        )

class PolyExtField(Field):
    # field
    F = abstractproperty()
    DEG = abstractproperty()
    MOD_COEFF = abstractproperty()

    def fmap(self, coef):
        # map Maybe<int> top Field
        assert len(coef) == self.DEG
        return [self.F(p) for p in coef]

    def op(self, rhs):
        return self.functor([x + y for x, y in zip(self.id, rhs.id)])

    @classmethod
    def sec_identity(cls):
        field = cls.F
        return cls([field(1)] + [field(0)] * (cls.DEG - 1))

    @classmethod
    def identity(cls):
        field = cls.F
        return cls([field(0)] * cls.DEG)

    def inverse(self):
        return self.functor([-x for x in self.id])


    def sec_inverse(self):
        field = self.F
        lm, hm = [field(1)] + [field(0)] * self.DEG, [field(0)] * (self.DEG + 1)
        low, high = self.id + [field(0)], self.MOD_COEFF + [field(1)]
        while deg(low, field):
            r = poly_rounded_div(high, low, field)
            r += [field(0)] * (self.DEG + 1 - len(r))
            nm = [field(x) for x in hm]
            new = [field(x) for x in high]
            assert len(lm) == len(hm) == len(low) == len(high) == len(nm) == len(new) == self.DEG + 1
            for i in range(self.DEG + 1):
                for j in range(self.DEG + 1 - i):
                    nm[i+j] -= lm[i] * r[j]
                    new[i+j] -= low[i] * r[j]
            lm, low, hm, high = nm, new, lm, low
        return self.functor([i / field(low[0]) for i in lm[:self.DEG]])

    def sec_op(self, rhs):
        # Let m(x) be a fixed polynomial of F[x] of degree d.
        # By the Division Algorithm, for any polynomial p(x)
        # (ref: https://www.aplustopper.com/division-algorithm-for-polynomials/)
        # there is a unique polynomial r(x)
        # determined by:
        # * deg(r(x))< d
        # * p(x)−r(x) is a multiple of m(x) in F[x]
        # For a(x),b(x) in F[x]_d we define multiplication modulom(x) by
        # a(x)·b(x) =r(x) (mod m(x)
        # where r(x) is the remainder of a(x)b(x) upon division by m(x).

        field = self.F
        # b = [0, 0, 0, ...]
        b = [field(0)] * (self.DEG * 2 - 1)

        for i in range(self.DEG):
            for j in range(self.DEG):
                b[i + j] = b[i + j] + self.id[i] * rhs.id[j]

        while len(b) > self.DEG:
            exp, top = len(b) - self.DEG - 1, b.pop()
            for i in range(self.DEG):
                b[exp + i] = b[exp + 1] - top * field(self.MOD_COEFF[i])
        return self.functor(b)




PrimeField = FiniteField
Fq = FiniteField
