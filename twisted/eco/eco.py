import sexpy
import operator
import types

def consify(sexp):
    if sexp and isinstance(sexp, types.ListType):
        qar = sexp[0]
        qdr = sexp[1:]
        return [consify(qar),consify(qdr)]
    else:
        return sexp

def eval(string):
    c = consify(sexpy.fromString(string))
    return evalExp(c, (None, {}))

def lookup(exp, env):
    val = None
    while 1:
        val = env[1].get(exp)
        if val:
            return val
        env = env[0]
        if not env:
            raise AttributeError("variable '%s' not found" % exp)


def extendEnv(oldEnv, bindings):
    d = {}
    while bindings:
        k = car(car(bindings))
        v = cadr(car(bindings))
        bindings = cdr(bindings)
        d[k.string] = evalExp(v, oldEnv)
    return (oldEnv, d)


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

def eval_apply(exp, env):
    evaledList = []
    args = cdr(exp)
    while args:
        evaledList.append(evalExp(car(args), env))
        args = cdr(args)
    funkyDict = {"+": func_add, "-": func_subtract}
    fname = 'func_'+car(exp).string
    return apply((globals().get(fname) or funkyDict.get(car(exp).string)), evaledList)

def evalExp(exp, env):
    if isinstance(exp, sexpy.Atom):
        return lookup(exp, env)
    elif isinstance(exp, types.ListType):
        if exp == []:
            return exp
        n = exp[0].string
        special_form = globals().get("eval_" + n)
        if special_form:
            return special_form(cdr(exp), env)
        else:
            # macro = globals().get("macro_" + n)
            # if macro:
            #   return evalExp(macroexpand(macro), env)
            return eval_apply(exp, env)
    else:
        return exp

def eval_if(exp, env):
    test = car(exp)
    then = cadr(exp)
    els  = caddr(exp)
    if evalExp(test, env):
        return evalExp(then, env)
    else:
        return evalExp(els, env)


def eval_let(exp, env):
    newEnv = extendEnv(env, car(exp))
    exp = cdr(exp)
    while exp:
        rv = evalExp(car(exp), newEnv)
        exp = cdr(exp)
    return rv

#def eval_function(exp, env):
#    return lookup_function(car(exp))
    
#def eval_def(exp, env):
    
