# -*- test-case-name: twisted.logger.test.test_logger -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Logger class.
"""

from __future__ import annotations

from time import time
from types import TracebackType
from typing import Any, Callable, ContextManager, Optional, Protocol, cast

from twisted.python.compat import currentframe
from twisted.python.failure import Failure
from ._interfaces import ILogObserver, LogTrace
from ._levels import InvalidLogLevelError, LogLevel


class Operation(Protocol):
    """
    An L{Operation} represents the success (or lack thereof) of code performed
    within the body of the L{Logger.failureHandler} context manager.
    """

    @property
    def succeeded(self) -> bool:
        """
        Did the operation succeed?  C{True} iff the code completed without
        raising an exception; C{False} while the code is running and C{False}
        if it raises an exception.
        """

    @property
    def failure(self) -> Failure | None:
        """
        Did the operation raise an exception?  If so, this L{Failure} is that
        exception.
        """

    @property
    def failed(self) -> bool:
        """
        Did the operation fail?  C{True} iff the code raised an exception;
        C{False} while the code is running and C{False} if it completed without
        error.
        """


class _FailCtxMgr:
    succeeded: bool = False
    failure: Failure | None = None

    def __init__(self, fail: Callable[[Failure], None]) -> None:
        self._fail = fail

    @property
    def failed(self) -> bool:
        return self.failure is not None

    def __enter__(self) -> Operation:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
        /,
    ) -> bool:
        if exc_type is not None:
            failure = Failure()
            self.failure = failure
            self._fail(failure)
        else:
            self.succeeded = True
        return True


class _FastFailCtxMgr:
    def __init__(self, fail: Callable[[Failure], None]) -> None:
        self._fail = fail

    def __enter__(self) -> None:
        pass

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
        /,
    ) -> bool:
        if exc_type is not None:
            failure = Failure()
            self.failure = failure
            self._fail(failure)
        return True


class Logger:
    """
    A L{Logger} emits log messages to an observer.  You should instantiate it
    as a class or module attribute, as documented in L{this module's
    documentation <twisted.logger>}.

    @ivar namespace: the namespace for this logger
    @ivar source: The object which is emitting events via this logger
    @ivar observer: The observer that this logger will send events to.
    """

    @staticmethod
    def _namespaceFromCallingContext() -> str:
        """
        Derive a namespace from the module containing the caller's caller.

        @return: the fully qualified python name of a module.
        """
        try:
            return cast(str, currentframe(2).f_globals["__name__"])
        except KeyError:
            return "<unknown>"

    def __init__(
        self,
        namespace: Optional[str] = None,
        source: Optional[object] = None,
        observer: Optional["ILogObserver"] = None,
    ) -> None:
        """
        @param namespace: The namespace for this logger.  Uses a dotted
            notation, as used by python modules.  If not L{None}, then the name
            of the module of the caller is used.
        @param source: The object which is emitting events via this
            logger; this is automatically set on instances of a class
            if this L{Logger} is an attribute of that class.
        @param observer: The observer that this logger will send events to.
            If L{None}, use the L{global log publisher <globalLogPublisher>}.
        """
        if namespace is None:
            namespace = self._namespaceFromCallingContext()

        self.namespace = namespace
        self.source = source

        if observer is None:
            from ._global import globalLogPublisher

            self.observer: ILogObserver = globalLogPublisher
        else:
            self.observer = observer

    def __get__(self, instance: object, owner: Optional[type] = None) -> "Logger":
        """
        When used as a descriptor, i.e.::

            # File: athing.py
            class Something:
                log = Logger()
                def hello(self):
                    self.log.info("Hello")

        a L{Logger}'s namespace will be set to the name of the class it is
        declared on.  In the above example, the namespace would be
        C{athing.Something}.

        Additionally, its source will be set to the actual object referring to
        the L{Logger}.  In the above example, C{Something.log.source} would be
        C{Something}, and C{Something().log.source} would be an instance of
        C{Something}.
        """
        assert owner is not None

        if instance is None:
            source: Any = owner
        else:
            source = instance

        return self.__class__(
            ".".join([owner.__module__, owner.__name__]),
            source,
            observer=self.observer,
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.namespace!r}>"

    def emit(
        self, level: LogLevel, format: Optional[str] = None, **kwargs: object
    ) -> None:
        """
        Emit a log event to all log observers at the given level.

        @param level: a L{LogLevel}
        @param format: a message format using new-style (PEP 3101)
            formatting.  The logging event (which is a L{dict}) is
            used to render this format string.
        @param kwargs: additional key/value pairs to include in the event.
            Note that values which are later mutated may result in
            non-deterministic behavior from observers that schedule work for
            later execution.
        """
        if level not in LogLevel.iterconstants():
            self.failure(
                "Got invalid log level {invalidLevel!r} in {logger}.emit().",
                Failure(InvalidLogLevelError(level)),
                invalidLevel=level,
                logger=self,
            )
            return

        event = kwargs
        event.update(
            log_logger=self,
            log_level=level,
            log_namespace=self.namespace,
            log_source=self.source,
            log_format=format,
            log_time=time(),
        )

        if "log_trace" in event:
            cast(LogTrace, event["log_trace"]).append((self, self.observer))

        self.observer(event)

    def failure(
        self,
        format: str,
        failure: Optional[Failure] = None,
        level: LogLevel = LogLevel.critical,
        **kwargs: object,
    ) -> None:
        """
        Log a failure and emit a traceback.

        For example::

            try:
                frob(knob)
            except Exception:
                log.failure("While frobbing {knob}", knob=knob)

        or::

            d = deferredFrob(knob)
            d.addErrback(lambda f: log.failure("While frobbing {knob}",
                                               f, knob=knob))

        This method is meant to capture unexpected exceptions in code; an
        exception that is caught and handled somehow should be logged, if
        appropriate, via L{Logger.error} instead.  If some unknown exception
        occurs and your code doesn't know how to handle it, as in the above
        example, then this method provides a means to describe the failure.
        This is done at L{LogLevel.critical} by default, since no corrective
        guidance can be offered to an user/administrator, and the impact of the
        condition is unknown.

        @param format: a message format using new-style (PEP 3101) formatting.
            The logging event (which is a L{dict}) is used to render this
            format string.

        @param failure: a L{Failure} to log.  If L{None}, a L{Failure} is
            created from the exception in flight.

        @param level: a L{LogLevel} to use.

        @param kwargs: additional key/value pairs to include in the event.
            Note that values which are later mutated may result in
            non-deterministic behavior from observers that schedule work for
            later execution.

        @see: L{Logger.failureHandler}

        @see: L{Logger.failuresHandled}
        """
        if failure is None:
            failure = Failure()

        self.emit(level, format, log_failure=failure, **kwargs)

    def debug(self, format: Optional[str] = None, **kwargs: object) -> None:
        """
        Emit a log event at log level L{LogLevel.debug}.

        @param format: a message format using new-style (PEP 3101) formatting.
            The logging event (which is a L{dict}) is used to render this
            format string.

        @param kwargs: additional key/value pairs to include in the event.
            Note that values which are later mutated may result in
            non-deterministic behavior from observers that schedule work for
            later execution.
        """
        self.emit(LogLevel.debug, format, **kwargs)

    def info(self, format: Optional[str] = None, **kwargs: object) -> None:
        """
        Emit a log event at log level L{LogLevel.info}.

        @param format: a message format using new-style (PEP 3101) formatting.
            The logging event (which is a L{dict}) is used to render this
            format string.

        @param kwargs: additional key/value pairs to include in the event.
            Note that values which are later mutated may result in
            non-deterministic behavior from observers that schedule work for
            later execution.
        """
        self.emit(LogLevel.info, format, **kwargs)

    def warn(self, format: Optional[str] = None, **kwargs: object) -> None:
        """
        Emit a log event at log level L{LogLevel.warn}.

        @param format: a message format using new-style (PEP 3101) formatting.
            The logging event (which is a L{dict}) is used to render this
            format string.

        @param kwargs: additional key/value pairs to include in the event.
            Note that values which are later mutated may result in
            non-deterministic behavior from observers that schedule work for
            later execution.
        """
        self.emit(LogLevel.warn, format, **kwargs)

    def error(self, format: Optional[str] = None, **kwargs: object) -> None:
        """
        Emit a log event at log level L{LogLevel.error}.

        @param format: a message format using new-style (PEP 3101) formatting.
            The logging event (which is a L{dict}) is used to render this
            format string.

        @param kwargs: additional key/value pairs to include in the event.
            Note that values which are later mutated may result in
            non-deterministic behavior from observers that schedule work for
            later execution.
        """
        self.emit(LogLevel.error, format, **kwargs)

    def critical(self, format: Optional[str] = None, **kwargs: object) -> None:
        """
        Emit a log event at log level L{LogLevel.critical}.

        @param format: a message format using new-style (PEP 3101) formatting.
            The logging event (which is a L{dict}) is used to render this
            format string.

        @param kwargs: additional key/value pairs to include in the event.
            Note that values which are later mutated may result in
            non-deterministic behavior from observers that schedule work for
            later execution.
        """
        self.emit(LogLevel.critical, format, **kwargs)

    def failuresHandled(
        self, format: str, level: LogLevel = LogLevel.critical, **kwargs: object
    ) -> ContextManager[Operation]:
        """
        Run some application code, logging a failure and emitting a traceback
        in the event that any of it fails, but continuing on.  For example::

            log = Logger(...)

            def frameworkCode() -> None:
                with log.failuresHandled("While frobbing {knob}:", knob=knob) as op:
                    frob(knob)
                if op.succeeded:
                    log.info("frobbed {knob} successfully", knob=knob)

        This method is meant to capture unexpected exceptions from application
        code; an exception that is caught and handled somehow should be logged,
        if appropriate, via L{Logger.error} instead.  If some unknown exception
        occurs and your code doesn't know how to handle it, as in the above
        example, then this method provides a means to describe the failure.
        This is done at L{LogLevel.critical} by default, since no corrective
        guidance can be offered to an user/administrator, and the impact of the
        condition is unknown.

        @param format: a message format using new-style (PEP 3101) formatting.
            The logging event (which is a L{dict}) is used to render this
            format string.

        @param level: a L{LogLevel} to use.

        @param kwargs: additional key/value pairs to include in the event, if
            it is emitted.  Note that values which are later mutated may result
            in non-deterministic behavior from observers that schedule work for
            later execution.

        @see: L{Logger.failure}
        @see: L{Logger.failureHandler}

        @return: A context manager which yields an L{Operation} which will have
            either its C{succeeded} or C{failed} attribute set to C{True} upon
            completion of the code within the code within the C{with} block.
        """
        return _FailCtxMgr(lambda f: self.failure(format, f, level, **kwargs))

    def failureHandler(
        self,
        staticMessage: str,
        level: LogLevel = LogLevel.critical,
    ) -> ContextManager[None]:
        """
        For performance-sensitive frameworks that needs to handle potential
        failures from frequently-called application code, and do not need to
        include detailed structured information about the failure nor inspect
        the result of the operation, this method returns a context manager that
        will log exceptions and continue, that can be shared across multiple
        invocations.  It should be instantiated at module scope to avoid
        additional object creations.

        For example::

            log = Logger(...)
            ignoringFrobErrors = log.failureHandler("while frobbing:")

            def hotLoop() -> None:
                with ignoringFrobErrors:
                    frob()

        This method is meant to capture unexpected exceptions from application
        code; an exception that is caught and handled somehow should be logged,
        if appropriate, via L{Logger.error} instead.  If some unknown exception
        occurs and your code doesn't know how to handle it, as in the above
        example, then this method provides a means to describe the failure in
        nerd-speak.  This is done at L{LogLevel.critical} by default, since no
        corrective guidance can be offered to an user/administrator, and the
        impact of the condition is unknown.

        @param format: a message format using new-style (PEP 3101) formatting.
            The logging event (which is a L{dict}) is used to render this
            format string.

        @param level: a L{LogLevel} to use.

        @see: L{Logger.failure}

        @return: A context manager which does not return a value, but will
            always exit from exceptions.
        """
        return _FastFailCtxMgr(lambda f: self.failure(staticMessage, f, level))


_log = Logger()


def _loggerFor(obj: object) -> Logger:
    """
    Get a L{Logger} instance attached to the given class.
    """
    return _log.__get__(obj, obj.__class__)
