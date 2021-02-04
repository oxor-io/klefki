import ast
from time import time
from copy import deepcopy

class Flattener:
    def __init__(self, src, ctx={}):
        self.ops = ["set", "+", "-", "*", "/"]
        self.ctx = ctx
        raw = ast.parse(src.lstrip()).body
        assert len(raw) == 1 and isinstance(raw[0], ast.FunctionDef), "only support function"
        self.raw = raw[0]
        self.extra_inputs()
        self.syms = [i for i in self.inputs]
        self.extra_body()
        self._symbol = 0
        self.flatten_body()
        self.closure = {}

    def closure_alias(self, sym, refs):
        if not isinstance(sym, str):
            return sym
        if sym in self.ops:
            return sym
        return "Local<Rc(%s)>%s" % (refs, sym)

    def mk_symbol(self, base="Sym"):
        ret = "%s::%s" % (base, str(self._symbol))
        self._symbol += 1
        return ret

    def latest_sym(self, base):
        if not isinstance(base, str):
            return base
        base = base.split("::")[0]
        syms = [s for s in self.syms if s.split("::")[0] == base]
        if len(syms):
            return syms[-1]
        else:
            return base

    def extra_inputs(self):
        self.inputs = [arg.arg for arg in self.raw.args.args]

    def handle_subscript(self, s, index=None):
        assert isinstance(s, ast.Subscript)
        assert isinstance(s.slice, ast.Index)
        assert isinstance(s.value, ast.Name)
        if isinstance(s.slice.value, ast.Name):
            if index == None:
                index = self.ctx[s.slice.value.id]
        else:
            index = s.slice.value.value
        return ast.Num(self.ctx[s.value.id][index])


    def extra_loop(self, loop):
        """
        only support:
        for _ in range(3):
        """
        avalid_iter_arg = (ast.Constant, ast.Name)
        loop_index = loop.target.id
        assert loop.iter.func.id == "range"
        assert len(loop.iter.args) == 1
        assert isinstance(loop.iter.args[0], avalid_iter_arg)
        if isinstance(loop.iter.args[0], ast.Constant):
            times = loop.iter.args[0].value
        else:
            times = self.ctx[loop.iter.args[0].id]
        ret = [(i, deepcopy(loop.body)) for i in range(times)]
        for e in ret:
            for s in e[1]:
                if isinstance(s, ast.Assign) and isinstance(s.value, ast.Subscript):
                    s.value = self.handle_subscript(s.value, index=e[0])
        return sum([r[1] for r in ret], [])

    def extra_body(self):
        body = []
        avalid_stmt = (ast.Assign, ast.Return, ast.For, ast.Assert)
        returned = False
        for c in self.raw.body:
            assert isinstance(c, avalid_stmt)
            assert not returned
            if isinstance(c, ast.For):
                body += self.extra_loop(c)
                continue
            elif isinstance(c, ast.Return):
                returned = True
            body.append(c)
        self.body = body


    def flatten_body(self):
        self.flatten_code = sum([self.flatten_stmt(c) for c in self.body], [])


    def transfer_assert(self, stmt):
        assert isinstance(stmt.test, ast.Compare)
        assert len(stmt.test.ops) == 1
        assert isinstance(stmt.test.ops[0], ast.Eq)
        assert isinstance(stmt.test.left, ast.Name)
        target = stmt.test.left.id
        # dont make new symbol if assert
        # instead, use the latest symbol of target
        target = self.latest_sym(target)
        self.syms.append(target)
        value = stmt.test.comparators[0]
        return self.flatten_expr(target, value)


    def flatten_stmt(self, s):
        if isinstance(s, ast.Assign):
            assert len(s.targets) == 1 and isinstance(s.targets[0], ast.Name)
            target = s.targets[0].id
            if target in self.syms:
                target = self.mk_symbol(target)
            self.syms.append(target)
        elif isinstance(s, ast.Assert):
            return self.transfer_assert(s)

        elif isinstance(s, ast.Return):
            target = '~out'
        # Get inner content
        return self.flatten_expr(target, s.value)

    def flatten_expr(self, target, expr):
        avalid_expr = (ast.Name, ast.Num, ast.BinOp, ast.Call, ast.Constant)

        assert isinstance(expr, avalid_expr), expr
        # x = y
        if isinstance(expr, ast.Name):
            return [['set', target, self.latest_sym(expr.id)]]
        # x = 5
        elif isinstance(expr, ast.Num):
            return [['set', target, expr.n]]
        elif isinstance(expr, ast.Constant):
            return [['set', target, expr.value]]
        elif isinstance(expr, ast.BinOp):
            return self.flatten_binop(target, expr)
        elif isinstance(expr, ast.Call):
            return self.flatten_call(target, expr)

    def flatten_call(self, target, expr):
        fn_ins = self.ctx[expr.func.id]
        if not hasattr(fn_ins, "rc"):
            fn_ins.rc = -1
        fn_ins.rc += 1
        fn_flat = deepcopy(fn_ins.flatcode)
        fn_inputs = fn_ins.inputs

        # tagging closure vars:
        for f in fn_flat:
            for i in range(len(f)):
                if isinstance(f[i], str):
                    # mark as local rc
                    if not f[i].split("::")[0] in fn_inputs:
                        f[i] = self.closure_alias(f[i], fn_ins.rc)
                    else:
                    # update global vars to latest
                        if f[i] in fn_inputs:
                            f[i] = self.latest_sym(fn_inputs.index(f[i]))
                        else:
                            f[i] = self.closure_alias(f[i], fn_ins.rc)


        fn_flat[-1][1] = target
        return fn_flat


    def flatten_binop(self, target, expr):
        avalid_binop = (ast.Mult, ast.Add, ast.Sub, ast.Div, ast.Pow)
        assert type(expr.op) in avalid_binop
        if isinstance(expr.op, ast.Add):
            op = '+'
        elif isinstance(expr.op, ast.Mult):
            op = '*'
        elif isinstance(expr.op, ast.Sub):
            op = '-'
        elif isinstance(expr.op, ast.Div):
            op = '/'
        elif isinstance(expr.op, ast.Pow):
            return self.flatten_pow(target, expr)

        if isinstance(expr.left, (ast.Name, ast.Num)):
            if isinstance(expr.left, ast.Name):
                var1 = self.latest_sym(expr.left.id)
            else:
                var1 = expr.left.n
            sub1 = []
        # If one of the subexpressions is itself a compound expression, recursively
        # apply this method to it using an intermediate variable
        else:
            var1 = self.mk_symbol()
            sub1 = self.flatten_expr(var1, expr.left)
        # Same for right subexpression as for left subexpression
        if isinstance(expr.right, (ast.Name, ast.Num)):
            if isinstance(expr.right, ast.Name):
                var2 = self.latest_sym(expr.right.id)
            else:
                var2 = expr.right.n
            sub2 = []
        else:
            var2 = self.mk_symbol()
            self.syms.append(var2)
            sub2 = self.flatten_expr(var2, expr.right)
        # Last expression represents the assignment; sub1 and sub2 represent the
        # processing for the subexpression if any
        return sub1 + sub2 + [[op, target, var1, var2]]


    def flatten_pow(self, target, expr):
        assert isinstance(expr.right, ast.Num)
        if expr.right.n == 0:
            return [['set', target, 1]]
        elif expr.right.n == 1:
            return flatten_expr(target, expr.left)
        else: # This could be made more efficient via square-and-multiply but oh well
            if isinstance(expr.left, (ast.Name, ast.Num)):
                nxt = base = expr.left.id if isinstance(expr.left, ast.Name) else expr.left.n
                o = []
            else:
                nxt = base = self.mk_symbol()
                o = self.flatten_expr(base, expr.left)
            for i in range(1, expr.right.n):
                latest = nxt
                nxt = target if i == expr.right.n - 1 else self.mk_symbol()
                o.append(['*', nxt, latest, base])
            return o
