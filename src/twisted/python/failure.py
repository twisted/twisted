# -*- test-case-name: twisted.test.test_failure -*-
# See also test suite twisted.test.test_pbfailure

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Asynchronous-friendly error mechanism.

See L{Failure}.
"""


# System Imports
from copy import copy as shallowCopy
import sys
from linecache import getline as getSourceLine
from inspect import getmro, isclass
from io import StringIO
from opcode import opmap
from types import TracebackType
from typing import (
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    NoReturn,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)
from typing_extensions import Protocol as TypeProtocol

from twisted.python.reflect import safe_repr, safe_str, qual


_T = TypeVar("_T")


count = 0
traceupLength = 4


_Symbols = Sequence[Tuple[str, object]]
_FrameTuple = Tuple[str, str, int, _Symbols, _Symbols]


class DefaultException(Exception):
    pass


class _Writable(TypeProtocol):
    # Returns object because we don't care about the return type and if we type
    # it as None, TextIO base (which return int) doesn't match.
    def write(self, s: str) -> object:
        pass


def format_frames(
    frames: Sequence[_FrameTuple],
    write: Callable[[str], object],
    detail: str = "default",
) -> None:
    """
    Format and write frames.

    @param frames: is a sequence of frames as used by Failure.frames, with
        each frame being a tuple of
        (funcName, fileName, lineNumber, locals.items(), globals.items())
    @param write: this will be called with formatted strings.
    @param detail: Four detail levels are available:
        default, brief, verbose, and verbose-vars-not-captured.
        C{Failure.printDetailedTraceback} uses the latter when the caller asks
        for verbose, but no vars were captured, so that an explicit warning
        about the missing data is shown.
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
            w("    %s\n" % getSourceLine(filename, lineno).strip())
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
                w("  {} : {}\n".format(name, repr(val)))
            w(" ( Globals )\n")
            for name, val in globalVars:
                w("  {} : {}\n".format(name, repr(val)))


# trial uses this constant to check for this value
EXCEPTION_CAUGHT_HERE = "--- <exception caught here> ---"


class NoCurrentExceptionError(Exception):
    """
    Raised when trying to create a Failure from the current interpreter
    exception state and there is no current exception state.
    """


class _Frame:
    """
    A fake frame object, used by L{_Traceback}.

    @ivar f_code: fake L{code<types.CodeType>} object
    @ivar f_lineno: line number
    @ivar f_globals: fake f_globals dictionary (usually empty)
    @ivar f_locals: fake f_locals dictionary (usually empty)
    @ivar f_back: previous stack frame (towards the caller)
    """

    def __init__(self, frameinfo: _FrameTuple, back: Optional["_Frame"]) -> None:
        """
        @param frameinfo: (methodname, filename, lineno, locals, globals)
        @param back: previous (older) stack frame
        """
        name, filename, lineno, localz, globalz = frameinfo
        self.f_code = _Code(name, filename)
        self.f_lineno = lineno
        self.f_globals: Dict[str, object] = {}
        self.f_locals: Dict[str, object] = {}
        self.f_back = back


class _TracebackFrame:
    """
    Traceback-like object which can be passed to functions in the standard
    library L{traceback} module.
    """

    def __init__(self, frame: _Frame) -> None:
        self.tb_frame = frame
        self.tb_lineno = frame.f_lineno
        self.tb_next: Optional[_TracebackFrame] = None


def _Traceback(
    stackFrames: Sequence[_FrameTuple], tbFrames: Sequence[_FrameTuple]
) -> _TracebackFrame:
    """
    Construct a fake traceback object using a list of frames. Note that
    although frames generally include locals and globals, this information
    is not kept by the returned object, since locals and globals are not used in
    standard tracebacks.

    @param stackFrames: stack frames
    @param tbFrames: traceback frames
    """
    assert len(tbFrames) > 0, "Must pass some frames"
    # We deliberately avoid using recursion here, as the frames list may be
    # long.

    # 'stackFrames' is a list of frames above (ie, older than) the point the
    # exception was caught, with oldest at the start. Start by building these
    # into a linked list of _Frame objects (with the f_back links pointing back
    # towards the oldest frame).
    stack = None
    for sf in stackFrames:
        stack = _Frame(sf, stack)

    # 'tbFrames' is a list of frames from the point the exception was caught,
    # down to where it was thrown, with the oldest at the start. Add these to
    # the linked list of _Frames, but also wrap each one with a _Traceback
    # frame which is linked in the opposite direction (towards the newest
    # frame).
    stack = _Frame(tbFrames[0], stack)
    firstTb = tb = _TracebackFrame(stack)
    for sf in tbFrames[1:]:
        stack = _Frame(sf, stack)
        tb = tb.tb_next = _TracebackFrame(stack)

    # Return the first _TracebackFrame.
    return firstTb


class _Code:
    """
    A fake code object, used by L{_Traceback} via L{_Frame}.
    """

    def __init__(self, name: str, filename: str) -> None:
        self.co_name = name
        self.co_filename = filename


_inlineCallbacksExtraneous = []


_CallableT = TypeVar("_CallableT", bound=Callable[..., object])


def _extraneous(f: _CallableT) -> _CallableT:
    """
    Mark the given callable as extraneous to inlineCallbacks exception
    reporting; don't show these functions.

    @param f: a function that you NEVER WANT TO SEE AGAIN in ANY TRACEBACK
        reported by Failure.

    @return: f
    """
    _inlineCallbacksExtraneous.append(f.__code__)
    return f


_ExceptionT = TypeVar("_ExceptionT", bound=BaseException)


class Failure(BaseException):
    """
    A basic abstraction for an error that has occurred.

    This is necessary because Python's built-in error mechanisms are
    inconvenient for asynchronous communication.

    The C{stack} and C{frame} attributes contain frames.  Each frame is a tuple
    of (funcName, fileName, lineNumber, localsItems, globalsItems), where
    localsItems and globalsItems are the contents of
    C{locals().items()}/C{globals().items()} for that frame, or an empty tuple
    if those details were not captured.

    @ivar value: The exception instance responsible for this failure.
    @ivar type: The exception's class.
    @ivar stack: list of frames, innermost last, excluding C{Failure.__init__}.
    @ivar frames: list of frames, innermost first.
    """

    # The opcode of "yield" in Python bytecode. We need this in
    # _findFailure in order to identify whether an exception was
    # thrown by a throwExceptionIntoGenerator.
    # on PY3, b'a'[0] == 97 while in py2 b'a'[0] == b'a' opcodes
    # are stored in bytes so we need to properly account for this
    # difference.
    _yieldOpcode = opmap["YIELD_VALUE"]

    def __init__(
        self,
        exc_value: Optional[BaseException] = None,
        exc_type: Optional[Type] = None,
        exc_tb: Optional[TracebackType] = None,
        captureVars: bool = False,
    ) -> None:
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
        self.captureVars = captureVars
        self.type: Type[BaseException]
        self.value: BaseException
        self.pickled = 0

        tb = None

        if isinstance(exc_value, str) and exc_type is None:  # type: ignore[unreachable]
            raise TypeError("Strings are not supported by Failure")

        stackOffset = 0

        if exc_value is None:
            exc_value = self._findFailure()

        if exc_value is None:
            exc_type, exc_value, tb = sys.exc_info()
            if exc_type is None:
                raise NoCurrentExceptionError()
            assert exc_value is not None
            self.type = exc_type
            self.value = exc_value
            stackOffset = 1
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

        failure = getattr(self.value, "__failure__", None)
        if failure is not None:
            # For exceptions propagated through coroutine-awaiting (see
            # Deferred.send, AKA Deferred.__next__), which can't be raised as
            # Failure because that would mess up the ability to except: them:
            self._extrapolate(failure)

            # Clean up the inherently circular reference established by storing
            # the failure there.  This should make the common case of a Twisted
            # / Deferred-returning coroutine somewhat less hard on the garbage
            # collector.
            delattr(self.value, "__failure__")
            return

        if tb is None:
            if exc_tb:
                tb = exc_tb
            else:
                # Python 3
                tb = getattr(self.value, "__traceback__", tb)

        self.frames: List[_FrameTuple] = []
        self.stack: List[_FrameTuple] = []

        frames = self.frames
        stack = self.stack

        # Added 2003-06-23 by Chris Armstrong. Yes, I actually have a
        # use case where I need this traceback object, and I've made
        # sure that it'll be cleaned up.
        self.tb = tb

        if tb:
            f = tb.tb_frame
        elif not isinstance(self.value, Failure):
            # We don't do frame introspection since it's expensive,
            # and if we were passed a plain exception with no
            # traceback, it's not useful anyway
            f = None
            stackOffset = 0

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
            if captureVars:
                f_locals = f.f_locals.copy()
                if f.f_locals is f.f_globals:
                    f_globals: Dict[str, object] = {}
                else:
                    f_globals = f.f_globals.copy()
                for d in f_globals, f_locals:
                    if "__builtins__" in d:
                        del d["__builtins__"]
                localz = cast(Sequence[Tuple[str, object]], f_locals.items())
                globalz = cast(Sequence[Tuple[str, object]], f_globals.items())
            else:
                localz = globalz = ()
            stack.insert(
                0,
                (
                    f.f_code.co_name,
                    f.f_code.co_filename,
                    f.f_lineno,
                    localz,
                    globalz,
                ),
            )
            f = f.f_back

        while tb is not None:
            f = tb.tb_frame
            if captureVars:
                f_locals = f.f_locals.copy()
                if f.f_locals is f.f_globals:
                    f_globals = {}
                else:
                    f_globals = f.f_globals.copy()
                for d in f_globals, f_locals:
                    if "__builtins__" in d:
                        del d["__builtins__"]
                localz = list(f_locals.items())
                globalz = list(f_globals.items())
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
        if isclass(self.type) and issubclass(self.type, Exception):
            parentCs = getmro(self.type)
            self.parents: List[Union[Type, str]] = list(map(qual, parentCs))
        else:
            self.parents = [self.type]

    def _extrapolate(self, otherFailure: "Failure") -> None:
        """
        Extrapolate from one failure into another, copying its stack frames.

        @param otherFailure: Another L{Failure}, whose traceback information,
            if any, should be preserved as part of the stack presented by this
            one.
        """
        # Copy all infos from that failure (including self.frames).
        self.__dict__ = shallowCopy(otherFailure.__dict__)

        # If we are re-throwing a Failure, we merge the stack-trace stored in
        # the failure with the current exception's stack.  This integrated with
        # throwExceptionIntoGenerator and allows to provide full stack trace,
        # even if we go through several layers of inlineCallbacks.
        _, _, tb = sys.exc_info()
        frames: List[_FrameTuple] = []
        while tb is not None:
            f = tb.tb_frame
            if f.f_code not in _inlineCallbacksExtraneous:
                frames.append(
                    (f.f_code.co_name, f.f_code.co_filename, tb.tb_lineno, (), ())
                )
            tb = tb.tb_next
        # Merging current stack with stack stored in the Failure.
        frames.extend(self.frames)
        self.frames = frames

    def trap(self, *errorTypes: Type[_ExceptionT]) -> Type[_ExceptionT]:
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
        """
        error = self.check(*errorTypes)
        if error is None:
            self.raiseException()
        else:
            return error

    def check(self, *errorTypes: Type[_ExceptionT]) -> Optional[Type[_ExceptionT]]:
        """
        Check if this failure's type is in a predetermined list.

        @returns: the matching L{Exception} type, or None if no match.
        """
        for error in errorTypes:
            if isclass(error) and issubclass(error, Exception):
                err = qual(error)
            else:
                err = cast(str, error)
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
    def throwExceptionIntoGenerator(self, g: Generator[_T, object, object]) -> _T:
        """
        Throw the original exception into the given generator,
        preserving traceback information if available.

        @return: The next value yielded from the generator.
        @raise StopIteration: If there are no more values in the generator.
        @raise anything else: Anything that the generator raises.
        """
        # Note that the actual magic to find the traceback information
        # is done in _findFailure.
        return g.throw(self.type, self.value, self.tb)

    @classmethod
    def _findFailure(cls) -> Optional["Failure"]:
        """
        Find the failure that represents the exception currently in context.
        """
        tb = sys.exc_info()[-1]
        if not tb:
            return None

        secondLastTb = None
        lastTb = tb
        while lastTb.tb_next:
            secondLastTb = lastTb
            lastTb = lastTb.tb_next

        lastFrame = lastTb.tb_frame

        # NOTE: f_locals.get('self') is used rather than
        # f_locals['self'] because psyco frames do not contain
        # anything in their locals() dicts.  psyco makes debugging
        # difficult anyhow, so losing the Failure objects (and thus
        # the tracebacks) here when it is used is not that big a deal.

        # Handle raiseException-originated exceptions
        if lastFrame.f_code is cls.raiseException.__code__:
            return lastFrame.f_locals.get("self")

        # Handle throwExceptionIntoGenerator-originated exceptions
        # this is tricky, and differs if the exception was caught
        # inside the generator, or above it:

        # It is only really originating from
        # throwExceptionIntoGenerator if the bottom of the traceback
        # is a yield.
        # Pyrex and Cython extensions create traceback frames
        # with no co_code, but they can't yield so we know it's okay to
        # just return here.
        if (not lastFrame.f_code.co_code) or lastFrame.f_code.co_code[
            lastTb.tb_lasti
        ] != cls._yieldOpcode:
            return None

        # If the exception was caught above the generator.throw
        # (outside the generator), it will appear in the tb (as the
        # second last item):
        if secondLastTb:
            secondLastFrame = secondLastTb.tb_frame
            if secondLastFrame.f_code is cls.throwExceptionIntoGenerator.__code__:
                return secondLastFrame.f_locals.get("self")

        # If the exception was caught below the generator.throw
        # (inside the generator), it will appear in the frames' linked
        # list, above the top-level traceback item (which must be the
        # generator frame itself, thus its caller is
        # throwExceptionIntoGenerator).
        backFrame = tb.tb_frame.f_back
        if backFrame and backFrame.f_code is cls.throwExceptionIntoGenerator.__code__:
            return backFrame.f_locals.get("self")

        return None

    def __repr__(self) -> str:
        return "<{} {}: {}>".format(
            qual(self.__class__),
            qual(self.type),
            self.getErrorMessage(),
        )

    def __str__(self) -> str:
        return "[Failure instance: %s]" % self.getBriefTraceback()

    def __getstate__(self) -> Dict[str, object]:
        """Avoid pickling objects in the traceback."""
        if self.pickled:
            return self.__dict__
        c = self.__dict__.copy()

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

        # Added 2003-06-23. See comment above in __init__
        c["tb"] = None

        if self.stack is not None:
            # XXX: This is a band-aid.  I can't figure out where these
            # (failure.stack is None) instances are coming from.
            c["stack"] = [
                [
                    v[0],
                    v[1],
                    v[2],
                    _safeReprVars(v[3]),
                    _safeReprVars(v[4]),
                ]
                for v in self.stack
            ]

        c["pickled"] = 1
        return c

    def cleanFailure(self) -> None:
        """
        Remove references to other objects, replacing them with strings.

        This will also set the C{__traceback__} attribute of the exception
        instance to L{None}.
        """
        self.__dict__ = self.__getstate__()
        self.value.__traceback__ = None

    def getTracebackObject(self) -> Optional[TracebackType]:
        """
        Get an object that represents this Failure's stack that can be passed
        to traceback.extract_tb.

        If the original traceback object is still present, return that. If this
        traceback object has been lost but we still have the information,
        return a traceback-like object that is usable with the standard library
        L{traceback} module.

        If there is no traceback information at all, return L{None}.
        """
        if self.tb is not None:
            return self.tb
        elif len(self.frames) > 0:
            return cast(TracebackType, _Traceback(self.stack, self.frames))
        else:
            return None

    def getErrorMessage(self) -> str:
        """
        Get a string of the exception which caused this Failure.
        """
        if isinstance(self.value, Failure):
            return self.value.getErrorMessage()
        return safe_str(self.value)

    def getBriefTraceback(self) -> str:
        io = StringIO()
        self.printBriefTraceback(file=io)
        return io.getvalue()

    def getTraceback(
        self, elideFrameworkCode: bool = False, detail: str = "default"
    ) -> str:
        io = StringIO()
        self.printTraceback(
            file=io, elideFrameworkCode=elideFrameworkCode, detail=detail
        )
        return io.getvalue()

    def printTraceback(
        self,
        file: Optional[_Writable] = None,
        elideFrameworkCode: bool = False,
        detail: str = "default",
    ) -> None:
        """
        Emulate Python's standard error reporting mechanism.

        @param file: If specified, a file-like object to which to write the
            traceback.

        @param elideFrameworkCode: A flag indicating whether to attempt to
            remove uninteresting frames from within Twisted itself from the
            output.

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
                "{}: {}: {}\n".format(
                    hasFrames, safe_str(self.type), safe_str(self.value)
                )
            )
        else:
            w("Traceback (most recent call last):\n")

        # Frames, formatted in appropriate style
        if self.frames:
            if not elideFrameworkCode:
                format_frames(self.stack[-traceupLength:], w, formatDetail)
                w(f"{EXCEPTION_CAUGHT_HERE}\n")
            format_frames(self.frames, w, formatDetail)
        elif not detail == "brief":
            # Yeah, it's not really a traceback, despite looking like one...
            w("Failure: ")

        # Postamble, if any
        if not detail == "brief":
            w("{}: {}\n".format(qual(self.type), safe_str(self.value)))

        # Chaining
        if isinstance(self.value, Failure):
            # TODO: indentation for chained failures?
            file.write(" (chained Failure)\n")
            self.value.printTraceback(file, elideFrameworkCode, detail)
        if detail == "verbose":
            w("*--- End of Failure #%d ---\n" % self.count)

    def printBriefTraceback(
        self, file: Optional[_Writable] = None, elideFrameworkCode: bool = False
    ) -> None:
        """
        Print a traceback as densely as possible.
        """
        self.printTraceback(file, elideFrameworkCode, detail="brief")

    def printDetailedTraceback(
        self, file: Optional[_Writable] = None, elideFrameworkCode: bool = False
    ) -> None:
        """
        Print a traceback with detailed locals and globals information.
        """
        self.printTraceback(file, elideFrameworkCode, detail="verbose")


def _safeReprVars(
    varsDictItems: Iterable[Tuple[str, object]]
) -> Sequence[Tuple[str, str]]:
    """
    Convert a list of (name, object) pairs into (name, repr) pairs.

    L{twisted.python.reflect.safe_repr} is used to generate the repr, so no
    exceptions will be raised by faulty C{__repr__} methods.

    @param varsDictItems: a sequence of (name, value) pairs as returned by e.g.
        C{locals().items()}.
    @returns: a sequence of (name, repr) pairs.
    """
    return [(name, safe_repr(obj)) for (name, obj) in varsDictItems]


# slyphon: make post-morteming exceptions tweakable

DO_POST_MORTEM = True


def _debuginit(
    self: Failure,
    exc_value: Optional[BaseException] = None,
    exc_type: Optional[Type] = None,
    exc_tb: Optional[TracebackType] = None,
    captureVars: bool = False,
    Failure__init__: Callable[
        [
            Failure,
            Optional[BaseException],
            Optional[Type],
            Optional[TracebackType],
            bool,
        ],
        None,
    ] = Failure.__init__,
) -> None:
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


def startDebugMode() -> None:
    """
    Enable debug hooks for Failures.
    """
    Failure.__init__ = _debuginit  # type: ignore[assignment]
