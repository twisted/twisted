
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


"""
This is the beginnings of a Python virtual machine in Python.
"""

import dis
import types

cmp_op = (
    'LESS',                    #0, <
    'LESS_OR_EQUAL',           #1, <=
    'EQUAL',                   #2, ==
    'NOT_EQUAL',               #3, != <>
    'GREATER',                 #4, >
    'GREATER_OR_EQUAL',        #5, >=
    'IN',                      #6, in
    'NOT_IN',                  #7, not in
    'IS',                      #8, is
    'IS_NOT',                  #9, is not
    'EXCEPTION_MATCH',         #10, exception match
    'BAD',                     #11
    )

TRUE = 1
FALSE = 0


class Object:
    """Each of these operators will return a frame.

    If they can calculate the return value immediately, they will push the
    return onto the frame; otherwise they'll return a different frame, that
    will return the correct value when executed.
    """

    def __init__(self, value):
        self.check(value)
        self.value = value
    
    def operator_pos(self, frame):
        frame.push(+self.value)
        return frame
        
    def operator_neg(self, frame):
        frame.push(-self.value)
        return frame

    def operator_getattr(self, attr, frame):
        return frame

    def operator_getitem(self, item, frame):
        self.push(wrap(self.value[item]))
        return frame

    def operator_setitem(self, item, value, frame):
        self.value[item] = value
        return frame

    def operator_add(self, other, frame):
        if isinstance(other, self.__class__):
            frame.push(self.value + other.value)
        return frame

    def operator_call(self, args, kw, frame):
        frame.push(None)
        return frame

    def become_boolean(self, frame):
        if self.value:
            frame.push(TRUE)
        else:
            frame.push(FALSE)
        return frame

    def become_string(self, frame):
        frame.push(TRUE)
        return frame


class Number(Object):
    pass


class Int(Number):
    def check(self, value):
        assert type(value) == types.IntType


class Float(Number):
    def check(self, value):
        assert type(value) == types.FloatType


class Long(Number):
    def check(self, value):
        assert type(value) == types.LongType


class String(Object):
    def check(self, value):
        assert type(value) == types.StringType


class Tuple(Object):
    def check(self, value):
        assert type(value) == types.TupleType


class List(Object):
    def check(self, value):
        assert type(value) == types.ListType


def safe(func, globals):
    return Function(Code(func.func_code), func.func_defaults, globals)


class Function(Object):
    def __init__(self, code, defaults, globals):
        self.func_code = code
        self.func_doc = code.co_consts[0]
        self.func_defaults = defaults
        self.func_globals = globals

    def operator_call(self, args, kw, old):
        argmap = {}
        if len(args) > self.func_code.co_argcount:
            print args
            assert 0, 'too many args'
        for argn in range(len(args)):
            argmap[self.func_code.co_varnames[argn]] = args[argn]
        # TODO: assertions about redefinition
        for k, v in kw.values():
            assert isinstance(k, String), "varnames must be strings!!"
            argmap[k.value] = v
        if len(argmap) != self.func_code.co_argcount:
            assert 0, 'not enough args; needed %s got %s' % (self.func_code.co_argcount, len(argmap))
        new = Frame(self.func_code, old, old.f_builtins, argmap, self.func_globals, old.interp)
        return new

class Class(Object):
    def __init__(self, dict, bases, name):
        self.dict = dict
        self.bases = bases
        self.name = name

    def operator_call(self, args, kw, frame):
        inst = Instance(self)
        f = Function(Code(instance_create.func_code), (), {})
        newargs = (self, inst, args, kw)
        newkw = {}
        return f.operator_call(newargs, newkw, frame)

    def operator_getattr(self, attr, frame):
        if self.dict.has_key(attr):
            obj = self.dict[attr]
            if isinstance(obj, Function):
                obj = Method(self, None, obj)
            frame.push(obj)
            return frame
        obj = None
        if attr == '__dict__':
            obj = self.dict
        elif attr == '__bases__':
            obj = self.bases
        elif attr == '__name__':
            obj = self.name
        if obj is not None:
            frame.push(wrap(obj))
            return frame
        if self.dict.has_key(attr):
            if isinstance(self.dict[attr], Function):
                return Method(self, None, self.dict[attr])
        assert 0, "attribute error"
        


class Method(Object):
    def __init__(self, im_class, im_self, im_func):
        self.im_class = im_class
        self.im_self = im_self
        self.im_func = im_func

    def operator_call(self, args, kw, frame):
        if self.im_self is not None:
            return self.im_func.operator_call((self.im_self,)+args, kw, frame)
        else:
##            if not (isinstance(args[0], Instance) and args[0].classobj == self.im_self):
##                raise something
            return self.im_func.operator_call(args, kw, frame)

class Instance(Object):
    def __init__(self, classobj):
        self.classobj = classobj

    def operator_getattr(self, attr, frame):
        assert isinstance(attr, String)



class Code(Object):
    """This is a simulated code object.

    It is constructed from a real Python code object.
    """
    def check(self, obj):
        assert type(obj) == types.CodeType
        
    def __init__(self, codeobj):
        Object.__init__(self, codeobj)
        code = self.co_code = codeobj.co_code
        self.orig = codeobj
        self.co_consts = codeobj.co_consts
        self.co_names = codeobj.co_names
        self.co_varnames = codeobj.co_varnames
        self.co_argcount = codeobj.co_argcount
        self.opcodes = []
        self.jumps = {}
        i = 0
        n = len(code)
        while i < n:
            start = i
            # eat one byte
            c = code[i]
            i = i + 1
            op = ord(c)
            name = dis.opname[op]
            arg = None
            if op >= dis.HAVE_ARGUMENT:
                # eat two bytes.
                if name == 'CALL_FUNCTION':
                    arg = (ord(code[i]), ord(code[i+1]))
                else:
                    oparg = ord(code[i]) + (ord(code[i+1])*256)
                    if op in dis.hasconst:
                        arg = self.co_consts[oparg]
                    elif op in dis.hasname:
                        arg = self.co_names[oparg]
                    elif op in dis.hasjrel:
                        arg = oparg
                    elif op in dis.haslocal:
                        arg = self.co_varnames[oparg]
                    elif op in dis.hascompare:
                        arg = cmp_op[oparg]
                    else:
                        arg = oparg
                i = i + 2
            self.jumps[start] = len(self.opcodes)
            self.opcodes.append((start, name, arg))


class Block:
    def __init__(self, frame, typ, handler, stacklevel):
        self.frame = frame
        self.type = type
        self.handler = handler
        self.stacklevel = stacklevel

class Frame(Object):
    def __init__(self, code, back, builtins, locals, globals, interp):
        self.lineno = 0
        self.interp = interp
        self.f_code = code
        # exception state
        self.f_exc_traceback = None
        self.f_exc_type = None
        self.f_exc_value = None
        # variable bindings
        self.f_locals = locals
        self.f_globals = globals
        self.f_builtins = builtins
        # exception state or sys.settrace?
        self.f_trace = None
        # back pointer to previous stack frame
        self.f_back = back
        # last instruction executed (don't know if this is necessary...)
        self.f_lasti = 0
        # last bytecode sequence executed (offset into self.f_code.)
        self.f_lastb = 0
        # wtf?  python sure has some obscure corners...
        self.f_restricted = 1
        self.stack = []
        self.blockstack = []
        self.push = self.stack.append
        self.pop = self.stack.pop

    def op_POP_TOP(self, nothing):
        # without arg
        self.pop()
        return 1, self

    def op_ROT_TWO(self, nothing):
        v = self.pop()
        w = self.pop()
        self.push(v)
        self.push(w)
        return 1, self

    def op_ROT_THREE(self, nothing):
        v = self.pop()
        w = self.pop()
        x = self.pop()
        self.push(v)
        self.push(w)
        self.push(x)
        return 1, self

    def op_MAKE_FUNCTION(self, argc):
        defargs = []
        code = self.pop()
        for x in range(argc):
            defargs.insert(self.pop(),0)
        func = Function(code, defargs, self.f_globals)
        self.push(func)
        return 1, self

    def op_SETUP_EXCEPT(self, exceptdest):
        b = Block(self, 'except', self.f_lasti + exceptdest+3, len(self.stack))
        self.blockstack.append(b)
        return 1, self

    def op_SETUP_FINALLY(self, exceptdest):
        b = Block(self, 'finally', self.f_lasti + exceptdest+3, len(self.stack))
        self.blockstack.append(b)
        return 1, self

    def op_SETUP_LOOP(self, exceptdest):
        b = Block(self, 'loop', self.f_lasti + exceptdest+3, len(self.stack))
        self.blockstack.append(b)
        return 1, self

    def op_POP_BLOCK(self, none):
        self.blockstack.pop()
        return 1, self

    def op_END_FINALLY(self, none):
        print 'op end finally!'
        return 1, self

    def op_CALL_FUNCTION(self, (posparam, varparam)):
        args = []
        kw = {}
        for each in range(varparam):
            value = self.pop()
            key = self.pop()
            kw[key]=value
            
        for each in range(posparam):
            args.append(self.pop())
        func = self.pop()
        nf = func.operator_call(args, kw, self)
        return 1, nf

    def op_LOAD_ATTR(self, name):
        obj = self.pop()
        nf = obj.operator_getattr(name, self)
        return 1, nf

    def op_ROT_FOUR(self, nothing):
        u = self.pop();
        v = self.pop();
        w = self.pop();
        x = self.pop();
        self.push(u);
        self.push(x);
        self.push(w);
        self.push(v);
        return 1, self

    def op_DUP_TOP(self, nothing):
        v = self.stack[-1]
        self.push(v)
        return 1, self

    def op_STORE_FAST(self, name):
        self.f_locals[name] = self.pop()
        return 1, self

    op_STORE_NAME = op_STORE_FAST

    def op_LOAD_FAST(self, name):
        self.push(self.f_locals[name])
        return 1, self

    op_LOAD_NAME = op_LOAD_FAST

    def op_DUP_TOPX(self, arg):
        assert arg >= 1
        assert arg <= 5
        map(self.stack.append, self.stack[-arg:])
        return 1, self

    def op_LOAD_LOCALS(self, noarg):
        self.stack.append(self.f_locals)
        return 1, self

    def op_LOAD_GLOBAL(self, arg):
        self.push(self.f_globals[arg])
        return 1, self
        
    def op_BUILD_CLASS(self, noarg):
        dict = self.pop()
        bases = self.pop()
        name = self.pop()
        cl = Class(dict, bases, name)
        self.push(cl)
        return 1, self

    def op_UNARY_POSITIVE(self, noarg):
        v = self.pop()
        return 1, v.operator_pos(self)

    def op_UNARY_NEGATIVE(self, noarg):
        v = self.pop()
        return 1, v.operator_neg(self)

    def op_UNARY_NOT(self, noarg):
        v = self.pop()
        return 1, v.operator_not(self)

    def op_JUMP_IF_TRUE(self, fwd, t=TRUE, f=FALSE):
        v = self.stack[-1]
        if v is f:
            return 1, self
        elif v is t:
            # DO THE JUMP
            return self.op_JUMP_FORWARD(fwd)
        else:
            # take v off the stack
            self.pop()
            # 'cause this will put it back.
            return 0, v.become_boolean(self)

    def op_JUMP_FORWARD(self, fwd):
        JF_CODE_SIZE = 3
        self.f_lasti = self.f_lasti + fwd + JF_CODE_SIZE
        self.f_lastb = self.f_code.jumps[self.f_lasti]
        return 0, self
            
    def op_JUMP_IF_FALSE(self, fwd):
        return self.op_JUMP_IF_TRUE(fwd, FALSE, TRUE)

    def op_BINARY_ADD(self, noarg):
        TOS = self.pop()
        TOS1 = self.pop()
        # XXX TOS1 + TOS
        print TOS, TOS1
        self.push(TOS1.operator_add(TOS, self))
        return 1, self

    def op_LOAD_CONST(self, const):
        self.push(wrap(const))
        return 1, self

    def op_BUILD_TUPLE(self, count):
        tobe = []
        for ig in range(count):
            tobe.append(self.pop())
        self.push(wrap(tuple(tobe)))
        return 1, self
    
    def op_SET_LINENO(self, lineno):
        self.lineno = lineno
        return 1, self

    def op_PRINT_ITEM(self, noarg):
        TOS = self.pop()
        print "\t"+repr(TOS.value)
        return 1, self

    def op_PRINT_NEWLINE(self, noarg):
        return 1, self

    def op_RETURN_VALUE(self, noarg):
        retval = self.pop()
        if self.f_back is not None:
            self.f_back.push(retval)
        else:
            self.interp.gotret = 1
            self.interp.retval = retval
        return 0, self.f_back

    def work(self):
        opcode = self.f_code.opcodes[self.f_lastb]
        start, name, arg = opcode
        print self
        print self.stack
        print "%d   %s %s" % (start,name,arg)
        proc = getattr(self, "op_%s" % name)
        advance, frame = proc(arg)
        if advance:
            self.f_lastb = self.f_lastb + 1
            self.f_lasti = start
        return frame


class Interpreter:
    def __init__(self, code, builtins, globals):
        self.initial = Frame(code, None, builtins, globals, globals, self)
        self.frame = self.initial
        self.gotret = 0
        
    def timeslice(self):
        self.frame = self.frame.work()
        return self.gotret

    def run(self):
        while not self.timeslice():
            pass
        return self.retval



_wrapmap = {
    types.IntType: Int,
    types.StringType: String,
    types.FloatType: Float,
    types.LongType: Long,
    types.CodeType: Code,
    types.ListType: List,
    types.TupleType: Tuple,
    }


def wrap(obj):
    if obj is None:
        return None
    return _wrapmap[type(obj)](obj)



### operator overloading crap.
def instance_create(klass, inst, args, kw):
    try:
        func = klass.__init__
    except AttributeError:
        return inst
    else:
        func((inst,)+args, kw)

def instance_add(a, b):
    try:
        aadd = a.__add__
    except:
        try:
            badd = b.__radd__
        except:
            raise TypeError("__add__ nor __radd__ defined for these operands")
        else:
            return badd(a)
    else:
        return aadd(b)


if __name__ == '__main__':
    def rawthunk(arg):
        print 'called thunk with', arg
    
    def rawclasstest():
        class foo:
            x = 1
        f = foo()
    
    def dostuff(self):
    ##    n = 7
    ##    thunk(1)
    ##    classtest()
    ##    if n:
    ##        print 'hi'
    ##    else:
    ##        print 'bye'
        class foo:
            x = 1
            def __init__(self):
                print self
        f = foo()
        return 1
    dis.dis(dostuff)
    c = Code(dostuff.func_code)
    i = Interpreter(c, {},
                    {'thunk':safe(rawthunk,{}),
                     'classtest':safe(rawclasstest,{})}
                    )
    print i.run().value
