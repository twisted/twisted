# -*- test-case-name: twisted.trial.test.test_adapters -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>

import types, os, os.path as osp
from cStringIO import StringIO

from twisted.trial import itrial, reporter
from twisted.python import util as tputil, failure, reflect
from twisted.internet import defer

import zope.interface as zi

HIDE_TRIAL_INTERNALS = reporter.HIDE_TRIAL_INTERNALS

def _overrideMe(ignore):
    raise NotImplementedError, "you need to set the .adapter attribute"

class PersistentAdapterFactory(object):
    """I keep track of adapters to interfaces, returning the existing instance
    of an adapter for an original object if it exists, else, creating one
    @note: you need to register an B{INSTANCE} of this class as an adapter, not
    the B{CLASS ITSELF}!
    """
    adapter = _overrideMe

    def __init__(self):
        self.__registry = {}

    def __call__(self, original):
        return self.__registry.setdefault(original, self.adapter(original))


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

def getModuleFromMethodType(obj):
    return reflect.namedModule(obj.im_class.__module__)

# -- traceback formatting ---------------------

# many apologies for this, but getting around the component architecture to
# restore this functionality in a sane way was impossible.  -glyph
_tbformathack = {
    'plain': 'default',
    'emacs': 'brief',
    }

def formatFailureTraceback(fail):
    from twisted import trial as hack
    detailLevel = _tbformathack.get(hack.tbformat, 'default')
    elideFrameworkCode = HIDE_TRIAL_INTERNALS
    result = fail.getTraceback(detail=detailLevel, elideFrameworkCode=elideFrameworkCode)
    if detailLevel == 'default':
        # Apparently trial's tests doen't like the 'Traceback:' line.
        result = '\n'.join(result.split('\n')[1:])
    return result

def formatMultipleFailureTracebacks(failList):
    if failList:
        s = '\n'.join(["\n%s" % itrial.IFormattedFailure(fail)
                       for fail in failList])
        return s
    return ''

def formatTestMethodFailures(testMethod):
    return itrial.IFormattedFailure(testMethod.errors + testMethod.failures)

# -- IErrorReport and IImportErrorReport -------

from twisted.trial.reporter import DOUBLE_SEPARATOR, SUCCESS, SKIP
from twisted.trial.reporter import UNEXPECTED_SUCCESS, WORDS

def formatError(tm): # would need another adapter for tbformat='emacs'
    ret = [DOUBLE_SEPARATOR,
           '%s: %s (%s)\n' % (WORDS[tm.status], tm.name,
                              itrial.IFQClassName(tm.klass))]

    for msg in tm.skip, itrial.ITodo(tm.todo).msg:
        if msg is not None:
            ret.append(str(msg) + '\n')

    if tm.status not in (SUCCESS, SKIP, UNEXPECTED_SUCCESS):
        return "%s\n%s" % ('\n'.join(ret),
                             itrial.IFormattedFailure(tm.errors + tm.failures))
    return '\n'.join(ret)
    
def trimFilename(name, N):
    """extracts the last N path elements of a path and returns them
    as a string, preceeded by an elipsis and separated by os.sep
    """
    # XXX: this function is *not* perfect
    # if N > num path elements you still get an elipsis prepended
    L = []
    drive, name = osp.splitdrive(name)
    while 1:
        head, tail = osp.split(name)
        L.insert(0, tail)
        if not head or head == os.sep:
            break
        name = head
    if drive:
        L.insert(0, drive)

    if len(L) <= N:
        ret = "%s" % (os.path.join(*L),)
    else:
        ret = "...%s" % os.path.join(*L[-N:])
    return ret

    
def formatDoctestError(tm):
    ret = [DOUBLE_SEPARATOR,
           '%s: %s (%s)\n' % (WORDS[tm.status], tm.name, trimFilename(tm.filename, 4))]

    return "%s\n%s" % ('\n'.join(ret),
                       itrial.IFormattedFailure(tm.errors + tm.failures))

def formatImportError(aTuple):
    """returns a string that represents an itrial.IImportErrorReport
    @param args: a tuple of (name, error)
    """
    name, error = aTuple
    ret = [DOUBLE_SEPARATOR, '\nIMPORT ERROR:\n\n']
    if isinstance(error, failure.Failure):
        what = itrial.IFormattedFailure(error)
    elif type(error) == types.TupleType:
        what = error.args[0]
    else:
        what = "%s\n" % error
    ret.append("Could not import %s: \n%s\n" % (name, what))
    return ''.join(ret)


