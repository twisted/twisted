import sexpy
import operator
import types
import pprint

## special prefixes:
# eval_foo(exp, env); special form
# func_foo(*args); python-defined regular function
# def_foo(name, forms); 'def' statement, for declaring global thingies.


# In the beginning, there was the cons, and it was good.
def consify(sexp):
    if sexp and isinstance(sexp, types.ListType):
        qar = sexp[0]
        qdr = sexp[1:]
        return [consify(qar),consify(qdr)]
    else:
        return sexp

# And then came the evaluator. There was much rejoicing!
def eval(string):
    c = consify(sexpy.fromString(string))
    env = (ValueEnvironment(), FunctionEnvironment())
    return evalExp(c, env)

def evalExp(exp, env):
    if isinstance(exp, sexpy.Atom):
        return lookup(exp, env, VAR)
    elif isinstance(exp, types.ListType):
        if exp == []:
            return exp
        n = exp[0].string
        specialForm = globals().get("eval_" + n)
        if specialForm:
            return specialForm(cdr(exp), env)
        else:
            # macro = globals().get("macro_" + n)
            # if macro:
            #   return evalExp(macroexpand(macro), env)
            return eval_apply(exp, env)
    else:
        return exp


# And then He created the Two Namespaces. Many people spoke out! They did
# not want the segregation, but lo, it was how it was to be.

globalValues = {"nil" : []}
globalFunctions = {}

VAR = 0
FUN = 1

def ValueEnvironment():
    return (None, globalValues)

def FunctionEnvironment():
    return (None, globalFunctions)

def lookup(exp, env, varOrFun):
    vars = env[varOrFun]
    val = None
    while 1:
        val = vars[1].get(exp)
        if val:
            return val
        vars = vars[0]
        if not vars:
            raise NameError("variable '%s' not found" % exp)

def extendEnv(varOrFun, oldEnv, bindings):
    d = {}
    while bindings:
        k = car(car(bindings))
        v = cadr(car(bindings))
        bindings = cdr(bindings)
        d[k.string] = evalExp(v, oldEnv)

    if varOrFun == VAR:
        e = ((oldEnv[0], d), oldEnv[1])
    else:
        e = (oldEnv[0], (oldEnv[1], d))
    return e



## The functions were angered by this segregation. They came in hoardes to
## plunder the lands of the variables -- But He defeated them! And He tamed
## them to serve His followers.

class Function:
    def __init__(self, forms, env):
        self.env = env
        self.llist = car(forms)
        self.body = cadr(forms)


    def __call__(self, *args):
        bindings = []
        i = 0
        crap = self.llist
        while crap:
            #print "crap is", crap
            var = car(crap)
            #print "binding", var, "to", args[i]
            bindings.append([var, args[i]])
            i = i + 1
            crap = cdr(crap)

        if len(args) != len(bindings):
            raise TypeError("Wrong number of arguments!")
        #pprint.pprint(bindings)
        bindings = consify(bindings)
        #pprint.pprint(bindings)
        
        newEnv = extendEnv(VAR, self.env, bindings)
        #print "evaluating", self.body
        return evalExp(self.body, newEnv)



### Dispatched stuff.

## special forms


## "muhahahahaha" -- Moshe
eval_fn = Function

def eval_apply(exp, env):
    #lookup order: python-defined functions, eco-defined functions.
    evaledList = []
    args = cdr(exp)
    while args:
        evaledList.append(evalExp(car(args), env))
        args = cdr(args)
        
    funkyDict = {"+": func_add, "-": func_subtract}
    name = car(exp).string
    
    global_fun = globals().get('func_' + name)
    funky_fun = funkyDict.get(name)
    try:
        local_fun = lookup(name, env, FUN)
    except NameError:
        local_fun = None

    f = global_fun or funky_fun or local_fun
    if f:
        return apply(f,
                     evaledList)
    else:
        raise NameError("No callable named %s" % name)


def eval_if(exp, env):
    test = car(exp)
    then = cadr(exp)
    els  = caddr(exp)
    if evalExp(test, env):
        return evalExp(then, env)
    else:
        return evalExp(els, env)


def eval_let(exp, env):
    newEnv = extendEnv(VAR, env, car(exp))
    exp = cdr(exp)
    while exp:
        rv = evalExp(car(exp), newEnv)
        exp = cdr(exp)
    return rv

def eval_def(exp, env):
    f = globals().get("def_" + car(exp).string)
    if f:
        f(cadr(exp), cddr(exp), env)
        
def def_fn(name, forms, env):
    globalFunctions[name] = Function(forms, env)



## python-defined functions

def func_map(fun, list):
    if list:
        return [fun(car(list)), func_map(fun, cdr(list))]
    else:
        return []

def func_reduce(fun, list):
    if not list:
        raise TypeError("Cannot pass empty list")
    elif not cdr(list):
        return car(list)
    else:
        return reduce_1(fun, cddr(list), fun(car(list), cadr(list)))

def reduce_1(fun, list, prevResult):
    if list:
        return reduce_1(fun, cdr(list), fun(prevResult, car(list)))
    else:
        return prevResult

# car/cdr and compositions

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

def func_subtract(*exp):
    return reduce(operator.sub, exp)

