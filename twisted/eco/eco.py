# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import sexpy
import operator
import types
import pprint
import string
import sys
atom = sexpy.Atom

## special prefixes:
# eval_foo(exp, env); special form
# func_foo(*args); python-defined regular function
# def_foo(name, forms); 'def' statement, for declaring global thingies.


# In the beginning, there was the cons, and it was good.
def consify(sexp):
    if sexp and isinstance(sexp, types.ListType):
        qar = sexp[0]
        try: maybe_dot = sexp[1]
        except IndexError: maybe_dot = None
        if maybe_dot == atom('.'):
            qdr = sexp[2]
        else:
            qdr = sexp[1:]
        return [consify(qar),consify(qdr)]
    else:
        return sexp

# And then came the evaluator. There was much rejoicing!
def eval(string):
    forms = sexpy.fromString(string)
    env = (ValueEnvironment(), FunctionEnvironment())
    for form in forms:
        c = consify(form)
        ret = evalExp(c, env)
    return ret

def evalFile(fileObj):
    return eval(fileObj.read())

def evalExp(exp, env):
    if isinstance(exp, atom):
        return lookup(exp, env, VAR)
    elif isinstance(exp, types.ListType):
        if func_null(exp):
            return exp
        n = exp[0].string
        specialForm = globals().get("eval_" + n)
        if specialForm:
            return specialForm(cdr(exp), env)
        else:
            # macro = globals().get("macro_" + n)
            # if macro:
            #   return evalExp(macroexpand(macro), env)
            return eco_apply(exp, env)
    else:
        return exp


def ValueEnvironment():
    return (None, globalValues)

def FunctionEnvironment():
    return (None, globalFunctions)

def lookup(exp, env, varOrFun):
    vars = env[varOrFun]
    val = None
    while 1:
        val = vars[1].get(exp)
        if val is not None:
            return val
        vars = vars[0]
        if not vars:
            raise NameError("variable '%s' not found" % exp)

def extendEnv(varOrFun, oldEnv, bindings):
    d = {}
    while bindings:
        k = car(car(bindings))
        v = cdr(car(bindings))
        bindings = cdr(bindings)
        d[k.string] = v

    if varOrFun == VAR:
        e = ((oldEnv[0], d), oldEnv[1])
    else:
        e = (oldEnv[0], (oldEnv[1], d))
    return e



class Function:
    def __init__(self, forms, env):
        self.env = env
        self.llist = car(forms)
        self.body = cadr(forms)

    def parseLambdaList(self, args):
        i = 0
        bindings = []
        crap = self.llist
        while crap:
            if func_consp(crap):
                b =  cons(car(crap), args[i])
            else:
                rgs = apply(func_list, args[i:])
                b = cons(crap, rgs)
            bindings = cons(b, bindings)
            i = i + 1
            if func_consp(crap):
                crap = cdr(crap)
            else:
                break
        return bindings
        

    def __call__(self, *args):
        bindings = self.parseLambdaList(args)        
        newEnv = extendEnv(VAR, self.env, bindings)
        return evalExp(self.body, newEnv)

class Macro(Function):
    def expand(self, args):
        bindings = self.parseLambdaList(args)    
        newEnv = extendEnv(VAR, self.env, bindings)
        return evalExp(self.body, newEnv)
        
    def __call__(self, env, *args):
        return evalExp(self.expand(args), env)

### Dispatched stuff.

## special forms


## "muhahahahaha" -- Moshe
eval_fn = Function

def eco_apply(exp, env):
    #lookup order: python-defined functions, eco-defined functions/macros.
    argVec = []
    args = cdr(exp)
    name = car(exp).string
    while args:
        argVec.append(car(args))
        args = cdr(args)
    global_fun = globals().get('func_' + name)

    try:
        local_fun = lookup(name, env, FUN)
    except NameError:
        local_fun = None

    f = global_fun or local_fun
    if f:
        if isinstance(f, Macro):
            return apply(f, (env,) + tuple(argVec))
        else:
             return apply(f, map(lambda x, env=env: evalExp(x, env), argVec))
    else:
        raise NameError("No callable named %s" % name)

def eval_apply(exp, env):
    eco_apply( func_map(lambda x, env=env: evalExp(x, env), exp), env)
    
    

def eval_function(exp, env):
    return  globals().get('func_' + car(exp).string) or lookup(car(exp).string, env, FUN)

def eval_if(exp, env):
    test = car(exp)
    then = cadr(exp)
    els  = caddr(exp)
    if evalExp(test, env):
        return evalExp(then, env)
    else:
        return evalExp(els, env)

def eval_quote(exp, env):
    return car(exp)

def eval_backquote(exp, env):
    return func_mapcan(lambda x, env=env: backquotize(x, env), car(exp))

def backquotize(exp, env):
    if func_consp(exp):
        if isinstance(car(exp), atom):
            if car(exp).string == "unquote":
                return func_list(evalExp(cadr(exp), env))
            elif car(exp).string == "unquote-splice":
                return evalExp(cadr(exp), env)
            elif car(exp).string == "backquote":
                return func_list(exp)
            else:
                return func_list(eval_backquote(func_list(exp), env))
        else:
            return func_list(eval_backquote(func_list(exp), env))
    else:
        return func_list(exp)
            
def eval_let(exp, env):
    newEnv = extendEnv(VAR, env, func_map(lambda x, env=env: cons(car(x), evalExp(cadr(x), env)), car(exp)))
    exp = cdr(exp)
    while exp:
        rv = evalExp(car(exp), newEnv)
        exp = cdr(exp)
    return rv

def eval_def(exp, env):
    f = globals().get("def_" + car(exp).string)
    if f:
        return f(cadr(exp).string, cddr(exp), env)
        
def def_fn(name, forms, env):
    x =  Function(forms, env)
    globalFunctions[name] = x
    return x
def def_macro(name, forms, env):
    x = Macro(forms, env)
    globalFunctions[name] = x
    return x

## python-defined functions

def func_map(fun, list):
    if list:
        return cons(fun(car(list)), func_map(fun, cdr(list)))
    else:
        return nil
def func_mapcan(fun, list):
    if list:
        output = []
        while list != nil:
            output.append(fun(car(list)))
            list = cdr(list)
        return apply(func_nconc, output)

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

def func_format(str, *args):
    return str % tuple(args)

def func_concat(strs, delim=''):
    s = []
    while strs:
        s.append(car(strs))
        strs = cdr(strs)
    return delim.join(s)

def func_macroexpand(sexp):
    if func_consp(sexp):
        a = car(sexp)
        d = cdr(sexp)
        if isinstance(a, atom):
            m = globalFunctions.get(a.string)
            if isinstance(m, Macro):
                args = func_map(func_macroexpand, d)
                argVec = []
                while args:
                    argVec.append(car(args))
                    args = cdr(args)
                return m.expand(argVec)
            elif a.string == 'let':
                bindings = func_map(lambda x: func_list(car(x),func_macroexpand(cadr(x))), car(d))
                body= func_map(func_macroexpand, cdr(d))
                return func_list(a, bindings, body)
            elif a.string == 'quote' or a.string == 'backquote':
                return sexp
            elif a.string == 'def':
                return func_list(a, car(d), cadr(d), func_map(func_macroexpand, cddr(d)))
            else:
                return cons(a, func_map(func_macroexpand, d))

    else:
        return sexp
                    
        

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
    for e in exp:
        if e:
            v = e
    return e or 0

def func_consp(exp):
    return isinstance(exp, types.ListType) and len(exp) == 2 

def func_or(*exp):
    for e in exp:
        if e:
            return e
    return 0

def func_not(a):
    return not a

def func_cons(car, cdr):
    return [car, cdr]
cons = func_cons

def func_setcar(lst, newcar):
    lst[0] = newcar

def func_setcdr(lst, newcdr):
    lst[1] = newcdr

def func_list(*exp):
    head = lispList = []
    for val in exp:
        newLispList = []
        lispList.append(val)
        lispList.append(newLispList)
        lispList = newLispList
    return head

def func_nconc(*lists):
    top = apply(func_list, lists)
    while 1:
        if not top:
            return nil        
        top_of_top = car(top)
        if func_consp(top_of_top):
            elements = cdr(top)
            splice = top_of_top
            while 1:
                if not elements:
                    break
                ele = car(elements)
                if func_consp(ele):
                    func_setcdr(func_last(splice), ele)
                    splice = ele
                elif func_null(ele):
                    func_setcdr(func_last(splice), ele)
                else:
                    if cdr(elements):
                        raise "argument is not a list"
                    else:
                        func_setcdr(func_last(splice), ele)
                    
                elements = cdr(elements)
            return top_of_top
        elif func_null(top_of_top):
            return nil
        else:
            if cdr(top):
                raise "argument is not a list"
            else:
                return top_of_top            
    top = cdr(top)

def func_null(exp):
    return exp == []

def func_last(lst):
    if func_null(cdr(lst)):
        return lst
    else:
        return func_last(cdr(lst))
    
def func_subtract(*exp):
    return reduce(operator.sub, exp)
 
globalFunctions =  {"+": func_add, "-": func_subtract}
globalValues = {"nil" : []}
nil = []
VAR = 0
FUN = 1

##############################################################################
# Here comes the fun part.

def cMacroExpand(form):
    if isinstance(form, types.StringType):
        return func_macroexpand(func_list(atom("cstring"), form))
    elif func_consp(form):
        if car(form) == 'comment':
            return func_list(atom('comment'), cadr(form))
        else:
            return cMacroExpand1(cons(car(form), func_map(cMacroExpand, cdr(form))))
    elif isinstance(form, atom):
        return form.string
    else:
        return form

def zoot(x):
    if func_consp(x):
        return cMacroExpand1(x)
    elif isinstance(x, atom):
        return x.string
    else:
        return x

func_cmacroexpand = cMacroExpand
def cMacroExpand1(form):

    a = 'cgen_' + car(form).string
    y = globals().get(a)
    if y:
        args = []
        i  = cdr(form)
        while i:
            args.append(zoot(car(i)))
            i = cdr(i)
        z = apply(y, args)
        if func_consp(z):
            return cMacroExpand1(z)
        else:
            return func_macroexpand(z)
    else:
        return func_macroexpand(form)


gensymCounter = 1

includes = sys.stdout

def cgen_cgensym(name=None):
    return(atom('_%s_%s' % (name or 'G', gensymCounter)))
def cgen_include(file):
    includes.write('\n#include "%s"\n' % file)
def cgen_sysinclude(file):
    includes.write("\n#include <%s>\n" % file)
globals()['func_sys-include'] = cgen_sysinclude

def prepArglist(specs):
    x = []
    while specs:
        t = []
        s = car(specs)
        while s:
            t.append(car(s))
            s = cdr(s)            
        x.append(string.join(map(lambda a: a.string, t), ' '))
        specs = cdr(specs)
    return string.join(x, ', ')
def mixCommas(args):
    return string.join(map(str, args), ", ")

def func_comment(text):
    return "/* %s */" % text
def func_str(obj):
    return str(obj)

def cgen_cstring(text):
    return '"%s"' % text 

def cgen_cblock(*statements):
    return "{%s}" % string.join(statements, ";\n")
globalFunctions['cblock'] = cgen_cblock
def cgen_call(funcname, *args):
    return "%s(%s)" % (funcname, mixCommas(args))
def cgen_cdeclare(type, variables):
    a = []
    while type !=nil:
        a.append(car(type).string + " ")
        type = cdr(type)    
    if func_consp(variables):        
        while variables != nil:
            a.append(car(variables))
            variables=cdr(variables)
    else:
        a.append(variables+";")
    return string.join(a,' ')

def cgen_typedef(type, name):
    return "typedef %s %s;" % (type, name)

def cgen_cstruct(body):
    return "struct %s" % body

globalFunctions['cstruct'] = cgen_cstruct

def cgen_enum(name,lst=None):
    if func_consp(name):
        a = ['enum']
        while name != nil:
            a.append(car(name))
            name=cdr(name)
    else:
        a = ['enum',name]
        if lst:
            while lst !=nil:
                while lst !=nil:
                    l = car(lst)
                    while l != nil:
                        a.append(car(l))
                        l = cdr(l)
                    lst=cdr(lst)                    
    return string.join(a, ' ')

def cgen_function(type,name,args, *body):
    a = []
    while type!=nil:
        a.append(car(type))
        type=cdr(type)        
    return "%s %s(%s) {\n%s}" % (string.join(map(lambda x: x.string, a), ' '), name, prepArglist(args), string.join(body,';\n'))

globalFunctions['c-function'] = cgen_function

def cgen_aref(name, index):
    return "%s[%s]" % (name, index)

def cgen_cast(type,body):
    return "((%s)%s)" % (type, body)

def cgen_deref(body):
    return "*" + body
def cgen_ref(body):
    return '&' + body
def cgen_pos(body):
    return '+' + body
def cgen_neg(body):
    return '-' + body
def cgen_tilde(body):
    return '~' + body
def cgen_bang(body):
    return '!' + body

def cgen_case(val,stmt):
    return "case %s: %s" % (val, stmt)

def cgen_default(stmt):
    return "default: " + stmt

def cgen_switch (val, *cases):
    return "switch (%s) {\n %s }\n" % (val, string.join(cases, '\n'))

def cgen_if(test, then, els=None):
    if els:
        x = ";}\n else " + els
    else:
        x = ";}\n"
    return "if (%s)\n {%s%s" % (test, then, x)

def cgen_for(init, test, iterate, body):
    return "for (%s;%s;%s) %s" % (init or '',test or '',iterate or '',body or '')

def cgen_do(stmt, test):
    return "do %s while (%s)" % (stmt, test)

def cgen_while(test, stmt):
    return "while (%s) %s" % (test, stmt)

def cgen_label(label,stmt):
    return "%s: %s" % (label, stmt)

def cgen_break():
    return "break"

def cgen_goto(label):
    return "goto " + label

def cgen_continue():
    return "continue"

def cgen_return(expr=""):
    return "return %s" % expr

def cgen_sizeof(value):
    return "sizeof " + value

globals()['cgen_sizeof-type'] = lambda type: "sizeof (%s)" % type
globals()['cgen_expr-if'] = lambda test,then,els:"((%s) ? (%s) : (%s))" % (test, then, els)
globals()['cgen_.'] = lambda x,y: "%s.%s" % (x,y)
globals()['cgen_->'] = lambda x,y: "%s->%s" % (x,y)
globals()['cgen_='] = lambda x,y: "%s = %s" % (x,y)
globals()['cgen_*='] = lambda x,y: "%s *= %s" % (x,y)
globals()['cgen_+='] = lambda x,y: "%s += %s" % (x,y)
globals()['cgen_-='] = lambda x,y: "%s -= %s" % (x,y)
globals()['cgen_/='] = lambda x,y: "%s /= %s" % (x,y)
globals()['cgen_&='] = lambda x,y: "%s &= %s" % (x,y)
globals()['cgen_^='] = lambda x,y: "%s ^= %s" % (x,y)
globals()['cgen_<<='] = lambda x,y: "%s <<= %s" % (x,y)
globals()['cgen_>>='] = lambda x,y: "%s >>= %s" % (x,y)
globals()['cgen_|='] = lambda x,y: "%s |= %s" % (x,y)
globals()['cgen_!='] = lambda x,y: "%s != %s" % (x,y)
globals()['cgen_=='] = lambda x,y: "%s == %s" % (x,y)
globals()['cgen_+'] = lambda x,y: "%s + %s" % (x,y)
globals()['cgen_^'] = lambda x,y: "%s ^ %s" % (x,y)
globals()['cgen_-'] = lambda x,y: "%s - %s" % (x,y)
globals()['cgen_*'] = lambda x,y: "%s * %s" % (x,y)
globals()['cgen_/'] = lambda x,y: "%s / %s" % (x,y)
globals()['cgen_%'] = lambda x,y: "%s % %s" % (x,y)
globals()['cgen_<<'] = lambda x,y: "%s << %s" % (x,y)
globals()['cgen_>>'] = lambda x,y: "%s >> %s" % (x,y)
globals()['cgen_<='] = lambda x,y: "%s <= %s" % (x,y)
globals()['cgen_>='] = lambda x,y: "%s >= %s" % (x,y)
globals()['cgen_&&'] = lambda x,y: "%s && %s" % (x,y)
globals()['cgen_||'] = lambda x,y: "%s || %s" % (x,y)

eval("""

[def macro struct [name defs . instance]
     (cstruct [format "%s %s %s" ',name
       [cblock ,@[map [fn [x] [concat [map [function str] x] " "]] defs]]
       ',[str [car [or instance [cons "" nil]]]]])]
  
[def macro cdefun [type name args . forms]
  (c-function ',type ',name ',[map [fn [a] [nconc [car a] [cdr a]]] args]
    ,@[map [function cmacroexpand] forms])]

[def macro cdeclare [type vars]
  (format "%s;" [cdeclare ,type ,[map [function cmacroexpand] vars]])]

[def macro defmain forms
  (cdefun [int] main  [[[int] argc] [[char * *] argv]]
    ,@forms)]

""")
