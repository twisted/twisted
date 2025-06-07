# -*- test-case-name: twisted.test.test_failure -*-
# See also test suite twisted.test.test_pbfailure

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Asynchronous-friendly error mechanism.

See L{Failure}.
"""

from __future__ import annotations

# System Imports
import builtins
import copy
import inspect
import linecache
import sys
from functools import partial
from inspect import getmro
from io import StringIO
from typing import Callable, NoReturn, TypeVar

from incremental import Version

from twisted.python import reflect
from twisted.python.deprecate import deprecatedProperty

_T_Callable = TypeVar("_T_Callable", bound=Callable[..., object])

count = 0
traceupLength = 4


class DefaultException(Exception):
    pass


def format_frames(frames, write, detail="default"):
    """
    Format and write frames.

    @param frames: is a list of frames as used by Failure.frames, with
        each frame being a list of
        (funcName, fileName, lineNumber, locals.items(), globals.items())
    @type frames: list
    @param write: this will be called with formatted strings.
    @type write: callable
    @param detail: Four detail levels are available:
        default, brief, verbose, and verbose-vars-not-captured.
        C{Failure.printDetailedTraceback} uses the latter when the caller asks
        for verbose, but no vars were captured, so that an explicit warning
        about the missing data is shown.
    @type detail: string
    """
    if detail not in ("default", "brief", "verbose", "verbose-vars-not-captured"):
        raise ValueError(
            "Detail must be default, brief, verbose, or "
            "verbose-vars-not-captured. (not %r)" % (detail,)
        )
    w = write
    if detail == "brief":
        for method, filename, lineno, localVars, globalVars in frames:
            w(f"{filename}:{lineno}:{method}\n")
    elif detail == "default":
        for method, filename, lineno, localVars, globalVars in frames:
            w(f'  File "{filename}", line {lineno}, in {method}\n')
            w("    %s\n" % linecache.getline(filename, lineno).strip())
    elif detail == "verbose-vars-not-captured":
        for method, filename, lineno, localVars, globalVars in frames:
            w("%s:%d: %s(...)\n" % (filename, lineno, method))
        w(" [Capture of Locals and Globals disabled (use captureVars=True)]\n")
    elif detail == "verbose":
        for method, filename, lineno, localVars, globalVars in frames:
            w("%s:%d: %s(...)\n" % (filename, lineno, method))
            w(" [ Locals ]\n")
            # Note: the repr(val) was (self.pickled and val) or repr(val)))
            for name, val in localVars:
                w(f"  {name} : {repr(val)}\n")
            w(" ( Globals )\n")
            for name, val in globalVars:
                w(f"  {name} : {repr(val)}\n")


# Unused, here for backwards compatibility.
EXCEPTION_CAUGHT_HERE = "--- <exception caught here> ---"


class NoCurrentExceptionError(Exception):
    """
    Raised when trying to create a Failure from the current interpreter
    exception state and there is no current exception state.
    """


def _Traceback(tbFrames):
    """
    Construct a fake traceback object using a list of frames.

    It should have the same API as stdlib to allow interaction with
    other tools.

    @param tbFrames: [(methodname, filename, lineno, locals, globals), ...]
    """
    assert len(tbFrames) > 0, "Must pass some frames"
    # We deliberately avoid using recursion here, as the frames list may be
    # long.

    stack = None
    # 'tbFrames' is a list of frames from the point the exception was caught,
    # down to where it was thrown, with the oldest at the start. Add these to
    # the linked list of _Frames, but also wrap each one with a _Traceback
    # frame which is linked in the opposite direction (towards the newest
    # frame).
    stack = _Frame(tbFrames[0], stack)
    firstTb = tb = _TracebackFrame(stack)
    for sf in tbFrames[1:]:
        stack = _Frame(sf, stack)
        tb.tb_next = _TracebackFrame(stack)
        tb = tb.tb_next

    # Return the first _TracebackFrame.
    return firstTb


# The set of attributes for _TracebackFrame, _Frame and _Code were taken from
# https://docs.python.org/3.11/library/inspect.html Other Pythons may have a
# few more attributes that should be added if needed.
class _TracebackFrame:
    """
    Fake traceback object which can be passed to functions in the standard
    library L{traceback} module.
    """

    def __init__(self, frame):
        """
        @param frame: _Frame object
        """
        self.tb_frame = frame
        self.tb_lineno = frame.f_lineno
        self.tb_lasti = frame.f_lasti
        self.tb_next = None


class _Frame:
    """
    A fake frame object, used by L{_Traceback}.

    @ivar f_code: fake L{code<types.CodeType>} object
    @ivar f_lineno: line number
    @ivar f_globals: fake f_globals dictionary (usually empty)
    @ivar f_locals: fake f_locals dictionary (usually empty)
    @ivar f_back: previous stack frame (towards the caller)
    """

    def __init__(self, frameinfo, back):
        """
        @param frameinfo: (methodname, filename, lineno, locals, globals)
        @param back: previous (older) stack frame
        @type back: C{frame}
        """
        name, filename, lineno, localz, globalz = frameinfo
        self.f_code = _Code(name, filename)
        self.f_lineno = lineno
        self.f_globals = dict(globalz or {})
        self.f_locals = dict(localz or {})
        self.f_back = back
        self.f_lasti = 0
        self.f_builtins = vars(builtins).copy()
        self.f_trace = None


class _Code:
    """
    A fake code object, used by L{_Traceback} via L{_Frame}.

    It is intended to have the same API as the stdlib code type to allow
    interoperation with other tools based on that interface.
    """

    def __init__(self, name, filename):
        self.co_name = name
        self.co_filename = filename
        self.co_lnotab = b""
        self.co_firstlineno = 0
        self.co_argcount = 0
        self.co_varnames = []
        self.co_code = b""
        self.co_cellvars = ()
        self.co_consts = ()
        self.co_flags = 0
        self.co_freevars = ()
        self.co_posonlyargcount = 0
        self.co_kwonlyargcount = 0
        self.co_names = ()
        self.co_nlocals = 0
        self.co_stacksize = 0

    def co_positions(self):
        return ((None, None, None, None),)


_inlineCallbacksExtraneous = []


def _extraneous(f: _T_Callable) -> _T_Callable:
    """
    Mark the given callable as extraneous to inlineCallbacks exception
    reporting; don't show these functions.

    @param f: a function that you NEVER WANT TO SEE AGAIN in ANY TRACEBACK
        reported by Failure.

    @type f: function

    @return: f
    """
    _inlineCallbacksExtraneous.append(f.__code__)
    return f


class Failure(BaseException):
    """
    A basic abstraction for an error that has occurred.

    This is necessary because Python's built-in error mechanisms are
    inconvenient for asynchronous communication.

    The C{frame} attribute contain the traceback frames.  Each frame is a tuple
    of (funcName, fileName, lineNumber, localsItems, globalsItems), where
    localsItems and globalsItems are the contents of
    C{locals().items()}/C{globals().items()} for that frame, or an empty tuple
    if those details were not captured.

    Local/global variables in C{frame} will only be captured if
    C{captureVars=True} when constructing the L{Failure}.

    @ivar value: The exception instance responsible for this failure.

    @ivar type: The exception's class.

    @ivar stack: Deprecated, always an empty list.  Equivalent information can
        be extracted from C{import traceback;
        traceback.extract_stack(your_failure.tb)}

    @ivar frames: list of frames, innermost first.
    """

    pickled = 0
    _parents = None

    def __init__(self, exc_value=None, exc_type=None, exc_tb=None, captureVars=False):
        """
        Initialize me with an explanation of the error.

        By default, this will use the current C{exception}
        (L{sys.exc_info}()).  However, if you want to specify a
        particular kind of failure, you can pass an exception as an
        argument.

        If no C{exc_value} is passed, then an "original" C{Failure} will
        be searched for. If the current exception handler that this
        C{Failure} is being constructed in is handling an exception
        raised by L{raiseException}, then this C{Failure} will act like
        the original C{Failure}.

        For C{exc_tb} only L{traceback} instances or L{None} are allowed.
        If L{None} is supplied for C{exc_value}, the value of C{exc_tb} is
        ignored, otherwise if C{exc_tb} is L{None}, it will be found from
        execution context (ie, L{sys.exc_info}).

        @param captureVars: if set, capture locals and globals of stack
            frames.  This is pretty slow, and makes no difference unless you
            are going to use L{printDetailedTraceback}.
        """
        global count
        count = count + 1
        self.count = count
        self.type = self.value = tb = None
        self.captureVars = captureVars

        if exc_value is None:
            self.type, self.value, tb = sys.exc_info()
            if self.type is None:
                raise NoCurrentExceptionError()
        elif exc_type is None:
            if isinstance(exc_value, Exception):
                self.type = exc_value.__class__
            else:
                # Allow arbitrary objects.
                self.type = type(exc_value)
            self.value = exc_value
        else:
            self.type = exc_type
            self.value = exc_value

        if isinstance(self.value, Failure):
            self._extrapolate(self.value)
            return

        if tb is None:
            if exc_tb:
                tb = exc_tb
            elif getattr(self.value, "__traceback__", None):
                # Python 3
                tb = self.value.__traceback__
        self.tb = tb

    @property
    def frames(self):
        if hasattr(self, "_frames"):
            return self._frames

        frames = self._frames = []
        tb = self.tb

        while tb is not None:
            f = tb.tb_frame
            if self.captureVars:
                localz = f.f_locals.copy()
                if f.f_locals is f.f_globals:
                    globalz = {}
                else:
                    globalz = f.f_globals.copy()
                for d in globalz, localz:
                    if "__builtins__" in d:
                        del d["__builtins__"]
                localz = list(localz.items())
                globalz = list(globalz.items())
            else:
                localz = globalz = ()
            frames.append(
                (
                    f.f_code.co_name,
                    f.f_code.co_filename,
                    tb.tb_lineno,
                    localz,
                    globalz,
                )
            )
            tb = tb.tb_next
        return frames

    @frames.setter
    def frames(self, frames):
        self._frames = frames

    @deprecatedProperty(Version("Twisted", 24, 10, 0))
    def stack(self):
        return []

    @stack.setter  # type: ignore[no-redef]
    def stack(self, stack):
        del stack

    @property
    def parents(self):
        if self._parents is not None:
            return self._parents

        if inspect.isclass(self.type) and issubclass(self.type, Exception):
            parentCs = getmro(self.type)
            self._parents = list(map(reflect.qual, parentCs))
        else:
            self._parents = [self.type]
        return self._parents

    @parents.setter
    def parents(self, parents):
        self._parents = parents

    def _extrapolate(self, otherFailure):
        """
        Extrapolate from one failure into another, copying its stack frames.

        @param otherFailure: Another L{Failure}, whose traceback information,
            if any, should be preserved as part of the stack presented by this
            one.
        @type otherFailure: L{Failure}
        """
        # Copy all infos from that failure (including self._frames).
        self.__dict__ = copy.copy(otherFailure.__dict__)

    @staticmethod
    def _withoutTraceback(value: BaseException) -> Failure:
        """
        Create a L{Failure} for an exception without a traceback.

        By restricting the inputs significantly, this constructor runs much
        faster.
        """
        result = Failure.__new__(Failure)
        global count
        count += 1
        result.captureVars = False
        result.count = count
        result.value = value
        result.type = value.__class__
        result.tb = None
        return result

    def trap(self, *errorTypes):
        """
        Trap this failure if its type is in a predetermined list.

        This allows you to trap a Failure in an error callback.  It will be
        automatically re-raised if it is not a type that you expect.

        The reason for having this particular API is because it's very useful
        in Deferred errback chains::

            def _ebFoo(self, failure):
                r = failure.trap(Spam, Eggs)
                print('The Failure is due to either Spam or Eggs!')
                if r == Spam:
                    print('Spam did it!')
                elif r == Eggs:
                    print('Eggs did it!')

        If the failure is not a Spam or an Eggs, then the Failure will be
        'passed on' to the next errback. In Python 2 the Failure will be
        raised; in Python 3 the underlying exception will be re-raised.

        @type errorTypes: L{Exception}
        """
        error = self.check(*errorTypes)
        if not error:
            self.raiseException()
        return error

    def check(self, *errorTypes):
        """
        Check if this failure's type is in a predetermined list.

        @type errorTypes: list of L{Exception} classes or
                          fully-qualified class names.
        @returns: the matching L{Exception} type, or None if no match.
        """
        for error in errorTypes:
            err = error
            if inspect.isclass(error) and issubclass(error, Exception):
                err = reflect.qual(error)
            if err in self.parents:
                return error
        return None

    def raiseException(self) -> NoReturn:
        """
        raise the original exception, preserving traceback
        information if available.
        """
        raise self.value.with_traceback(self.tb)

    @_extraneous
    def throwExceptionIntoGenerator(self, g):
        """
        Throw the original exception into the given generator,
        preserving traceback information if available.

        @return: The next value yielded from the generator.
        @raise StopIteration: If there are no more values in the generator.
        @raise anything else: Anything that the generator raises.
        """
        return g.throw(self.value.with_traceback(self.tb))

    def __repr__(self) -> str:
        return "<{} {}: {}>".format(
            reflect.qual(self.__class__),
            reflect.qual(self.type),
            self.getErrorMessage(),
        )

    def __str__(self) -> str:
        return "[Failure instance: %s]" % self.getBriefTraceback()

    def __setstate__(self, state):
        if "stack" in state:
            state.pop("stack")
        state["_parents"] = state.pop("parents")
        state["_frames"] = state.pop("frames")
        self.__dict__.update(state)

    def __getstate__(self):
        """
        Avoid pickling objects in the traceback.

        This is not called direclty by pickle, since C{BaseException}
        implements reduce; instead, pickle calls C{Failure.__reduce__} which
        then calls this API.
        """
        # Make sure _parents field is populated:
        _ = self.parents

        c = self.__dict__.copy()

        # Backwards compatibility with old code, e.g. for Perspective Broker:
        c["parents"] = c.pop("_parents")
        c["stack"] = []

        if "_frames" in c:
            c.pop("_frames")

        if self.captureVars:
            c["frames"] = [
                [
                    v[0],
                    v[1],
                    v[2],
                    _safeReprVars(v[3]),
                    _safeReprVars(v[4]),
                ]
                for v in self.frames
            ]
        else:
            c["frames"] = self.frames

        # Added 2003-06-23. See comment above in __init__
        c["tb"] = None

        c["pickled"] = 1
        return c

    def __reduce__(self):
        # BaseException implements a __reduce__ (in C, technically), so we need
        # to override this to get pickling working.
        return (partial(Failure.__new__, Failure), (), self.__getstate__())

    def cleanFailure(self):
        """
        Remove references to other objects, replacing them with strings.

        On Python 3, this will also set the C{__traceback__} attribute of the
        exception instance to L{None}.
        """
        state = self.__getstate__()
        state["_frames"] = state.pop("frames")
        self.__dict__ = state
        if getattr(self.value, "__traceback__", None):
            # Python 3
            self.value.__traceback__ = None

    def getTracebackObject(self):
        """
        Get an object that represents this Failure's stack that can be passed
        to traceback.extract_tb.

        If the original traceback object is still present, return that. If this
        traceback object has been lost but we still have the information,
        return a fake traceback object (see L{_Traceback}). If there is no
        traceback information at all, return None.
        """
        if self.tb is not None:
            return self.tb
        elif len(self.frames) > 0:
            return _Traceback(self.frames)
        else:
            return None

    def getErrorMessage(self) -> str:
        """
        Get a string of the exception which caused this Failure.
        """
        if isinstance(self.value, Failure):
            return self.value.getErrorMessage()
        return reflect.safe_str(self.value)

    def getBriefTraceback(self) -> str:
        io = StringIO()
        self.printBriefTraceback(file=io)
        return io.getvalue()

    def getTraceback(self, elideFrameworkCode: int = 0, detail: str = "default") -> str:
        io = StringIO()
        self.printTraceback(
            file=io, elideFrameworkCode=elideFrameworkCode, detail=detail
        )
        return io.getvalue()

    def printTraceback(self, file=None, elideFrameworkCode=False, detail="default"):
        """
        Emulate Python's standard error reporting mechanism.

        @param file: If specified, a file-like object to which to write the
            traceback.

        @param elideFrameworkCode: Deprecated, ignored.

        @param detail: A string indicating how much information to include
            in the traceback.  Must be one of C{'brief'}, C{'default'}, or
            C{'verbose'}.
        """
        if file is None:
            from twisted.python import log

            file = log.logerr

        w = file.write

        if detail == "verbose" and not self.captureVars:
            # We don't have any locals or globals, so rather than show them as
            # empty make the output explicitly say that we don't have them at
            # all.
            formatDetail = "verbose-vars-not-captured"
        else:
            formatDetail = detail

        # Preamble
        if detail == "verbose":
            w(
                "*--- Failure #%d%s---\n"
                % (self.count, (self.pickled and " (pickled) ") or " ")
            )
        elif detail == "brief":
            if self.frames:
                hasFrames = "Traceback"
            else:
                hasFrames = "Traceback (failure with no frames)"
            w(
                "%s: %s: %s\n"
                % (hasFrames, reflect.safe_str(self.type), reflect.safe_str(self.value))
            )
        else:
            w("Traceback (most recent call last):\n")

        # Frames, formatted in appropriate style
        if self.frames:
            format_frames(self.frames, w, formatDetail)
        elif not detail == "brief":
            # Yeah, it's not really a traceback, despite looking like one...
            w("Failure: ")

        # Postamble, if any
        if not detail == "brief":
            w(f"{reflect.qual(self.type)}: {reflect.safe_str(self.value)}\n")

        # Chaining
        if isinstance(self.value, Failure):
            # TODO: indentation for chained failures?
            file.write(" (chained Failure)\n")
            self.value.printTraceback(file, elideFrameworkCode, detail)
        if detail == "verbose":
            w("*--- End of Failure #%d ---\n" % self.count)

    def printBriefTraceback(self, file=None, elideFrameworkCode=0):
        """
        Print a traceback as densely as possible.
        """
        self.printTraceback(file, elideFrameworkCode, detail="brief")

    def printDetailedTraceback(self, file=None, elideFrameworkCode=0):
        """
        Print a traceback with detailed locals and globals information.
        """
        self.printTraceback(file, elideFrameworkCode, detail="verbose")


def _safeReprVars(varsDictItems):
    """
    Convert a list of (name, object) pairs into (name, repr) pairs.

    L{twisted.python.reflect.safe_repr} is used to generate the repr, so no
    exceptions will be raised by faulty C{__repr__} methods.

    @param varsDictItems: a sequence of (name, value) pairs as returned by e.g.
        C{locals().items()}.
    @returns: a sequence of (name, repr) pairs.
    """
    return [(name, reflect.safe_repr(obj)) for (name, obj) in varsDictItems]


# slyphon: make post-morteming exceptions tweakable

DO_POST_MORTEM = True


def _debuginit(
    self,
    exc_value=None,
    exc_type=None,
    exc_tb=None,
    captureVars=False,
    Failure__init__=Failure.__init__,
):
    """
    Initialize failure object, possibly spawning pdb.
    """
    if (exc_value, exc_type, exc_tb) == (None, None, None):
        exc = sys.exc_info()
        if not exc[0] == self.__class__ and DO_POST_MORTEM:
            try:
                strrepr = str(exc[1])
            except BaseException:
                strrepr = "broken str"
            print(
                "Jumping into debugger for post-mortem of exception '{}':".format(
                    strrepr
                )
            )
            import pdb

            pdb.post_mortem(exc[2])
    Failure__init__(self, exc_value, exc_type, exc_tb, captureVars)


def startDebugMode():
    """
    Enable debug hooks for Failures.
    """
    Failure.__init__ = _debuginit
