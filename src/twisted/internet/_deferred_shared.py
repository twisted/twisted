from typing import List, Optional

from twisted.logger import Logger
from twisted.python.failure import Failure

log = Logger()


class AlreadyCalledError(Exception):
    """
    This error is raised when one of L{Deferred.callback} or L{Deferred.errback}
    is called after one of the two had already been called.
    """


class CancelledError(Exception):
    """
    This error is raised by default when a L{Deferred} is cancelled.
    """


class DebugInfo:
    """
    Deferred debug helper.
    """

    failResult: Optional[Failure] = None
    creator: Optional[List[str]] = None
    invoker: Optional[List[str]] = None

    def _getDebugTracebacks(self) -> str:
        info = ""
        if self.creator is not None:
            info += " C: Deferred was created:\n C:"
            info += "".join(self.creator).rstrip().replace("\n", "\n C:")
            info += "\n"
        if self.invoker is not None:
            info += " I: First Invoker was:\n I:"
            info += "".join(self.invoker).rstrip().replace("\n", "\n I:")
            info += "\n"
        return info

    def __del__(self) -> None:
        """
        Print tracebacks and die.

        If the *last* (and I do mean *last*) callback leaves me in an error
        state, print a traceback (if said errback is a L{Failure}).
        """
        if self.failResult is not None:
            # Note: this is two separate messages for compatibility with
            # earlier tests; arguably it should be a single error message.
            log.critical("Unhandled error in Deferred:", isError=True)

            debugInfo = self._getDebugTracebacks()
            if debugInfo:
                format = "(debug: {debugInfo})"
            else:
                format = ""

            log.failure(format, self.failResult, debugInfo=debugInfo)
