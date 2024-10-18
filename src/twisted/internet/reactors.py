import sys
from typing import Callable, TypeVar

from .error import ReactorAlreadyInstalledError

_theGlobalReactor: object = None
_T = TypeVar("_T")


def installGlobalReactor(reactor: object) -> None:
    """
    Install reactor C{reactor}.

    @param reactor: An object that provides one or more IReactor* interfaces.

    @raises ReactorAlreadyInstalledError: if a global reactor is currently
        installed.
    """
    global _theGlobalReactor
    import twisted.internet

    # Do the legacy dance to make the importable module.
    if "twisted.internet.reactor" in sys.modules:
        raise ReactorAlreadyInstalledError("reactor already installed")
    twisted.internet.reactor = reactor  # type:ignore[attr-defined]
    sys.modules["twisted.internet.reactor"] = reactor  # type:ignore[assignment]

    _theGlobalReactor = reactor


def getGlobal(aspect: Callable[[object], _T]) -> _T:
    return aspect(_theGlobalReactor)


__all__ = [
    "installGlobalReactor",
    "getGlobal",
]
