# -*- test-case-name: twisted.test.test_failure -*-
# See also test suite twisted.test.test_pbfailure

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Asynchronous-friendly error mechanism.

See L{Failure}.
"""

# System Imports
import sys
import linecache
import string
from cStringIO import StringIO
import types

count = 0
traceupLength = 4

class DefaultException(Exception):
    pass

def format_frames(frames, write, detail="default"):
    """Format and write frames.

    @param frames: is a list of frames as used by Failure.frames, with
        each frame being a list of
        (funcName, fileName, lineNumber, locals.items(), globals.items())
    @type frames: list
    @param write: this will be called with formatted strings.
    @type write: callable
    @param detail: Three detail levels are available:
        default, brief, and verbose.
    @type detail: string
    """
    if detail not in ('default', 'brief', 'verbose'):
        raise ValueError, "Detail must be default, brief, or verbose. (not %r)" % (detail,)
    w = write
    if detail == "brief":
        for method, filename, lineno, localVars, globalVars in frames:
            w('%s:%s:%s\n' % (filename, lineno, method))
    elif detail == "default":
        for method, filename, lineno, localVars, globalVars in frames:
            w( '  File "%s", line %s, in %s\n' % (filename, lineno, method))
            w( '    %s\n' % string.strip(linecache.getline(filename, lineno)))
    elif detail == "verbose":
        for method, filename, lineno, localVars, globalVars in frames:
            w("%s:%d: %s(...)\n" % (filename, lineno, method))
            w(' [ Locals ]\n')
            # Note: the repr(val) was (self.pickled and val) or repr(val)))
            for name, val in localVars:
                w("  %s : %s\n" %  (name, repr(val)))
            w(' ( Globals )\n')
            for name, val in globalVars:
                w("  %s : %s\n" %  (name, repr(val)))

# slyphon: i have a need to check for this value in trial
#          so I made it a module-level constant
EXCEPTION_CAUGHT_HERE = "--- <exception caught here> ---" 



class NoCurrentExceptionError(Exception):
    """
    Raised when trying to create a Failure from the current interpreter
    exception state and there is no current exception state.
    """



class Failure:
    """A basic abstraction for an error that has occurred.

    This is necessary because Python's built-in error mechanisms are
    inconvenient for asynchronous communication.

    @ivar value: The exception instance responsible for this failure.
    @ivar type: The exception's class.
    """

    pickled = 0
    stack = None

    def __init__(self, exc_value=None, exc_type=None, exc_tb=None):
        """Initialize me with an explanation of the error.

        By default, this will use the current X{exception}
        (L{sys.exc_info}()).  However, if you want to specify a
        particular kind of failure, you can pass an exception as an
        argument.
        """
        global count
        count = count + 1
        self.count = count
        self.type = self.value = tb = None

        #strings Exceptions/Failures are bad, mmkay?
        if ((isinstance(exc_value, types.StringType) or
             isinstance(exc_value, types.UnicodeType))
            and exc_type is None):
            import warnings
            warnings.warn(
                "Don't pass strings (like %r) to failure.Failure (replacing with a DefaultException)." %
                exc_value, DeprecationWarning, stacklevel=2)
            exc_value = DefaultException(exc_value)

        stackOffset = 0
        if exc_value is None:
            self.type, self.value, tb = sys.exc_info()
            if self.type is None:
                raise NoCurrentExceptionError()
            stackOffset = 1
        elif exc_type is None:
            if isinstance(exc_value, Exception):
                self.type = exc_value.__class__
            else: #allow arbitrary objects.
                self.type = type(exc_value)
            self.value = exc_value
        else:
            self.type = exc_type
            self.value = exc_value
        if isinstance(self.value, Failure):
            self.__dict__ = self.value.__dict__
            return
        if tb is None:
            if exc_tb:
                tb = exc_tb
#             else:
#                 log.msg("Erf, %r created with no traceback, %s %s." % (
#                     repr(self), repr(exc_value), repr(exc_type)))
#                 for s in traceback.format_stack():
#                     log.msg(s)

        frames = self.frames = []
        stack = self.stack = []

        # added 2003-06-23 by Chris Armstrong. Yes, I actually have a
        # use case where I need this traceback object, and I've made
        # sure that it'll be cleaned up.
        self.tb = tb

        if tb:
            f = tb.tb_frame
        elif not isinstance(self.value, Failure):
            # we don't do frame introspection since it's expensive,
            # and if we were passed a plain exception with no
            # traceback, it's not useful anyway
            f = stackOffset = None
        
        while stackOffset and f:
            # This excludes this Failure.__init__ frame from the
            # stack, leaving it to start with our caller instead.
            f = f.f_back
            stackOffset -= 1

        # Keeps the *full* stack.  Formerly in spread.pb.print_excFullStack:
        #
        #   The need for this function arises from the fact that several
        #   PB classes have the peculiar habit of discarding exceptions
        #   with bareword "except:"s.  This premature exception
        #   catching means tracebacks generated here don't tend to show
        #   what called upon the PB object.

        while f:
            localz = f.f_locals.copy()
            if f.f_locals is f.f_globals:
                globalz = {}
            else:
                globalz = f.f_globals.copy()
            for d in globalz, localz:
                if d.has_key("__builtins__"):
                    del d["__builtins__"]
            stack.insert(0, [
                f.f_code.co_name,
                f.f_code.co_filename,
                f.f_lineno,
                localz.items(),
                globalz.items(),
                ])
            f = f.f_back

        while tb is not None:
            f = tb.tb_frame
            localz = f.f_locals.copy()
            if f.f_locals is f.f_globals:
                globalz = {}
            else:
                globalz = f.f_globals.copy()
            for d in globalz, localz:
                if d.has_key("__builtins__"):
                    del d["__builtins__"]
            
            frames.append([
                f.f_code.co_name,
                f.f_code.co_filename,
                tb.tb_lineno,
                localz.items(),
                globalz.items(),
                ])
            tb = tb.tb_next
        if isinstance(self.type, types.ClassType):
            parentCs = reflect.allYourBase(self.type)
            self.parents = map(reflect.qual, parentCs)
            self.parents.append(reflect.qual(self.type))
        else:
            self.parents = [self.type]

    def trap(self, *errorTypes):
        """Trap this failure if its type is in a predetermined list.

        This allows you to trap a Failure in an error callback.  It will be
        automatically re-raised if it is not a type that you expect.

        The reason for having this particular API is because it's very useful
        in Deferred errback chains:

        | def _ebFoo(self, failure):
        |     r = failure.trap(Spam, Eggs)
        |     print 'The Failure is due to either Spam or Eggs!'
        |     if r == Spam:
        |         print 'Spam did it!'
        |     elif r == Eggs:
        |         print 'Eggs did it!'

        If the failure is not a Spam or an Eggs, then the Failure
        will be 'passed on' to the next errback.

        @type errorTypes: L{Exception}
        """
        error = self.check(*errorTypes)
        if not error:
            raise self
        return error

    def check(self, *errorTypes):
        """Check if this failure's type is in a predetermined list.

        @type errorTypes: list of L{Exception} classes or
                          fully-qualified class names.
        @returns: the matching L{Exception} type, or None if no match.
        """
        for error in errorTypes:
            err = error
            if isinstance(error, types.ClassType) and issubclass(error, Exception):
                err = reflect.qual(error)
            if err in self.parents:
                return error
        return None

    def raiseException(self):
        """
        raise the original exception, preserving traceback
        information if available.
        """
        raise self.type, self.value, self.tb


    def __repr__(self):
        return "<%s %s>" % (self.__class__, self.type)

    def __str__(self):
        return "[Failure instance: %s]" % self.getBriefTraceback()

    def __getstate__(self):
        """Avoid pickling objects in the traceback.
        """
        if self.pickled:
            return self.__dict__
        c = self.__dict__.copy()
        
        c['frames'] = [
            [
                v[0], v[1], v[2],
                [(j[0], reflect.safe_repr(j[1])) for j in v[3]],
                [(j[0], reflect.safe_repr(j[1])) for j in v[4]]
            ] for v in self.frames
        ]

        # added 2003-06-23. See comment above in __init__
        c['tb'] = None

        if self.stack is not None:
            # XXX: This is a band-aid.  I can't figure out where these
            # (failure.stack is None) instances are coming from.
            c['stack'] = [
                [
                    v[0], v[1], v[2],
                    [(j[0], reflect.safe_repr(j[1])) for j in v[3]],
                    [(j[0], reflect.safe_repr(j[1])) for j in v[4]]
                ] for v in self.stack
            ]

        c['pickled'] = 1
        return c

    def cleanFailure(self):
        """Remove references to other objects, replacing them with strings.
        """
        self.__dict__ = self.__getstate__()

    def getErrorMessage(self):
        """Get a string of the exception which caused this Failure."""
        if isinstance(self.value, Failure):
            return self.value.getErrorMessage()
        return reflect.safe_str(self.value)

    def getBriefTraceback(self):
        io = StringIO()
        self.printBriefTraceback(file=io)
        return io.getvalue()

    def getTraceback(self, elideFrameworkCode=0, detail='default'):
        io = StringIO()
        self.printTraceback(file=io, elideFrameworkCode=elideFrameworkCode, detail=detail)
        return io.getvalue()

    def printTraceback(self, file=None, elideFrameworkCode=0, detail='default'):
        """Emulate Python's standard error reporting mechanism.
        """
        if file is None: file = log.logerr
        w = file.write

        # Preamble
        if detail == 'verbose':
            w( '*--- Failure #%d%s---\n' %
               (self.count,
                (self.pickled and ' (pickled) ') or ' '))
        elif detail == 'brief':
            if self.frames:
                hasFrames = 'Traceback'
            else:
                hasFrames = 'Traceback (failure with no frames)'
            w("%s: %s: %s\n" % (hasFrames, self.type, self.value))
        else:
            w( 'Traceback (most recent call last):\n')

        # Frames, formatted in appropriate style
        if self.frames:
            if not elideFrameworkCode:
                format_frames(self.stack[-traceupLength:], w, detail)
                w("%s\n" % (EXCEPTION_CAUGHT_HERE,))
            format_frames(self.frames, w, detail)
        elif not detail == 'brief':
            # Yeah, it's not really a traceback, despite looking like one...
            w("Failure: ")

        # postamble, if any
        if not detail == 'brief':
            w("%s: %s\n" % (reflect.safe_str(self.type),
                            reflect.safe_str(self.value)))
        # chaining
        if isinstance(self.value, Failure):
            # TODO: indentation for chained failures?
            file.write(" (chained Failure)\n")
            self.value.printTraceback(file, elideFrameworkCode, detail)
        if detail == 'verbose':
            w('*--- End of Failure #%d ---\n' % self.count)

    def printBriefTraceback(self, file=None, elideFrameworkCode=0):
        """Print a traceback as densely as possible.
        """
        self.printTraceback(file, elideFrameworkCode, detail='brief')

    def printDetailedTraceback(self, file=None, elideFrameworkCode=0):
        """Print a traceback with detailed locals and globals information.
        """
        self.printTraceback(file, elideFrameworkCode, detail='verbose')

# slyphon: make post-morteming exceptions tweakable

DO_POST_MORTEM = True

def _debuginit(self, exc_value=None, exc_type=None, exc_tb=None,
             Failure__init__=Failure.__init__.im_func):
    if (exc_value, exc_type, exc_tb) == (None, None, None):
        exc = sys.exc_info()
        if not exc[0] == self.__class__ and DO_POST_MORTEM:
            print "Jumping into debugger for post-mortem of exception '%s':" % exc[1]
            import pdb
            pdb.post_mortem(exc[2])
    Failure__init__(self, exc_value, exc_type, exc_tb)

def startDebugMode():
    """Enable debug hooks for Failures."""
    Failure.__init__ = _debuginit


def visualtest():
    def c():
        1/0

    def b():
        c()

    def a():
        b()

    def _frameworkCode(detailLevel, elideFrameworkCode):
        try:
            a()
        except:
            Failure().printTraceback(sys.stdout, detail=detailLevel, elideFrameworkCode=elideFrameworkCode)

    def _moreFrameworkCode(*a, **kw):
        return _frameworkCode(*a, **kw)

    def frameworkCode(*a, **kw):
        return _moreFrameworkCode(*a, **kw)

    print 'Failure visual test case:'
    for verbosity in ['brief', 'default', 'verbose']:
        for truth in True, False:
            print
            print '----- next ----'
            print 'detail: ',verbosity
            print 'elideFrameworkCode:', truth
            print
            frameworkCode(verbosity, truth)


# Sibling imports - at the bottom and unqualified to avoid unresolvable
# circularity
import reflect, log


if __name__ == '__main__':
    visualtest()
