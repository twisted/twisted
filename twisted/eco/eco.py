import sexpy
import operator
import types

globalValues = {"nil" : []}
globalFunctions = {}

def ValueEnvironment():
    return (None, globalValues)
def FunctionEnvironment():
    return (None, globalFunctions)

def consify(sexp):
    if sexp and isinstance(sexp, types.ListType):
        qar = sexp[0]
        qdr = sexp[1:]
        return [consify(qar),consify(qdr)]
    else:
        return sexp

def eval(string):
    c = consify(sexpy.fromString(string))
    return Evaluator().evalExp(c)

def lisp_map(fun, list):
    if list:
        return [fun(car(list)), lisp_map(fun, cdr(list))]
    else:
        return []

func_map = lisp_map

def lisp_reduce(fun, list):
    if not list:
        raise TypeError("Cannot pass empty list")
    elif not cdr(list):
        return car(list)
    else:
        return reduce_1(fun, cddr(list), fun(car(list), cadr(list)))

func_reduce = lisp_reduce

def lisp_reduce_1(fun, list, prevResult):
    if list:
        return reduce_1(fun, cdr(list), fun(prevResult, car(list)))
    else:
        return prevResult

def car(x):
    return x[0]
func_car = car

def cdr(x):
    return x[1]
func_cdr = cdr

def cadr(x):
    return x[1][0]
func_cadr = cadr

def caddr(x):
    return x[1][1][0]
func_caddr = caddr

def cddr(x):
    return x[1][1]
func_cddr = cddr

def func_eq(a, b):
    return a == b

def func_is(a, b):
    return a is b

def func_add(*exp):
    return reduce(operator.add, exp)

def func_and(*exp):
    return reduce(operator.__and__, exp)

def func_or(*exp):
    return reduce(operator.__or__, exp)

def func_not(a):
    return not a

def func_cons(car, cdr):
    return [car, cdr]

def func_list(*exp):
    head = lispList = []
    for val in exp:
        newLispList = []
        lispList.append(val)
        lispList.append(newLispList)
        lispList = newLispList
    return head

def func_subtract(exp, env):
    return reduce(operator.add, exp)


class Evaluator:
    def __init__(self):
        self.vals = ValueEnvironment()
        self.funs = FunctionEnvironment()
        
    def extendEnv(self, oldEnv, bindings):
        while bindings:
            k = car(car(bindings))
            v = cadr(car(bindings))
            bindings = cdr(bindings)
            d[k.string] = self.evalExp(v)
        return (oldEnv, d)
    
    def lookup(self, exp, env):
        val = None
        while 1:
            val = env[1].get(exp)
            if val:
                return val
            env = env[0]
            if not env:
                raise AttributeError("'%s' not found" % exp)

    def eval_apply(self, exp):
        evaledList = []
        args = cdr(exp)
        while args:
            evaledList.append(self.evalExp(car(args)))
            args = cdr(args)
            funkyDict = {"+": func_add, "-": func_subtract}
            fname = 'func_'+car(exp).string
        return apply((globals().get(fname) or funkyDict.get(car(exp).string)), evaledList)

    def evalExp(self, exp):
        if isinstance(exp, sexpy.Atom):
            return self.lookup(exp, self.vals)
        elif isinstance(exp, types.ListType):
            if exp == []:
                return exp
            n = exp[0].string
            special_form = getattr(self, "eval_" + n, None)
            if special_form:
                return special_form(cdr(exp))
            else:
                return self.eval_apply(exp)
        else:
            return exp

    def eval_if(self, exp):
        test = car(exp)
        then = cadr(exp)
        els  = caddr(exp)
        if self.evalExp(test):
            return self.evalExp(then)
        else:
            return self.evalExp(els)
        

    def eval_let(self, exp):
        self.vals = extendEnv(self.vals, car(exp))
        exp = cdr(exp)
        while exp:
            rv = self.evalExp(car(exp))
            exp = cdr(exp)
        return rv

    def eval_function(self, exp):
        return self.lookup(car(exp), self.funs)
    
#def eval_def(exp, env):
    
