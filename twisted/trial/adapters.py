import types
from cStringIO import StringIO

from twisted.trial import itrial, reporter
from twisted.python import util as tputil, failure, reflect
from twisted.internet import defer

import zope.interface as zi

HIDE_TRIAL_INTERNALS = reporter.HIDE_TRIAL_INTERNALS

# --- Some Adapters for 'magic' attributes ------------

class NewSkoolAdapter(object):
    def __init__(self, original):
        self.original = original

class TodoBase(NewSkoolAdapter):
    zi.implements(itrial.ITodo)
    types = msg = None

    def isExpected(self, fail):
        if self.types is None:
            return True
        for t in self.types:
            if fail.check(t):
                return True
        return False

    def __add__(self, other):
        return self.msg + other

class TupleTodo(TodoBase):
    def types(self):
        e = self.original[0]
        if isinstance(e, types.TupleType):
            return e
        elif e is None:
            return e
        else:
            return tuple([e])
    types = property(types)

    def msg(self):
        return self.original[1]
    msg = property(msg)

class StringTodo(TodoBase):
    def __init__(self, original):
        super(StringTodo, self).__init__(original)

        # XXX: How annoying should we *really* be?
        #
        #warnings.warn("the .todo attribute should now be a tuple of (ExpectedExceptionClass, message), "
        #              "see the twisted.trial.unittest docstring for info", stacklevel=2)

        self.types = None
        self.msg = original

class TimeoutBase(NewSkoolAdapter, tputil.FancyStrMixin):
    showAttributes = ('duration', 'excArg', 'excClass') 
    duration = excArg = None
    excClass = defer.TimeoutError
    _defaultTimeout, _defaultExcArg = 4.0, "deferred timed out after %s sec"

    def __init__(self, original):
        super(TimeoutBase, self).__init__(original)
##         if original is None:
##             self.duration = self._defaultTimeout
##             self.excArg = self._defaultExcArg % self.duration

    def __str__(self):
        return tputil.FancyStrMixin.__str__(self)
    __repr__ = __str__


class TupleTimeout(TimeoutBase):
    _excArg = None

    def __init__(self, original):
        super(TupleTimeout, self).__init__(original)
        self._set(*original)

    def _set(self, duration=None, excArg=None, excClass=None):
        for attr, param in [('duration', duration),
                            ('excClass', excClass),
                            ('excArg', excArg)]:
            if param is not None:
                setattr(self, attr, param)

    def _getExcArg(self):
        excArg = self._excArg
        if excArg is None:
            excArg = self._defaultExcArg % self.duration
        return excArg 

    def _setExcArg(self, val):
        self._excArg = val

    excArg = property(_getExcArg, _setExcArg)


class NumericTimeout(TimeoutBase):
    def __init__(self, original):
        self.duration = original 
        super(NumericTimeout, self).__init__(original)


# -- helpful internal adapters --

def getModuleNameFromModuleType(obj):
    return obj.__name__

def getModuleNameFromClassType(obj):
    # also for types.InstanceType
    return obj.__module__

def getModuleNameFromMethodType(obj):
    return obj.im_class.__module__

def getModuleNameFromFunctionType(obj):
    return obj.func_globals['__name__']
        
def getClassNameFromClass(obj):
    return obj.__name__

def getClassNameFromMethodType(obj):
    return obj.im_class.__name__

def getFQClassName(obj):
    return "%s.%s" % (itrial.IModuleName(obj), itrial.IClassName(obj))

def getFQMethodName(obj):
    return "%s.%s" % (itrial.IFQClassName(obj), obj.__name__)

def getClassFromMethodType(obj):
    return obj.im_class

def getModuleFromMethodType(obj):
    return reflect.namedModule(obj.im_class.__module__)

def getClassFromFQString(obj):
    return reflect.namedAny(obj)


# -- traceback formatting errors

def formatFailureTraceback(fail):
    if HIDE_TRIAL_INTERNALS:
        sio = StringIO()
        fail.printTraceback(sio)
        L = []
        for line in sio.getvalue().split('\n'):
            if (line.find(failure.EXCEPTION_CAUGHT_HERE) != -1) or L:
                L.append(line)
        return "\n".join(L[1:])
    return fail.getTraceback()

def formatMultipleFailureTracebacks(failList):
    if failList:
        s = '\n'.join(["%s\n\n" % itrial.IFormattedFailure(fail)
                       for fail in failList])
        return s
    return ''

def formatTestMethodFailures(testMethod):
    return itrial.IFormattedFailure(testMethod.errors + testMethod.failures)
