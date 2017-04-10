"""
Insults: a replacement for Curses/S-Lang.

Very basic at the moment."""

from eventually import deprecatedModuleAttribute
from incremental import Version

deprecatedModuleAttribute(
    Version("Twisted", 10, 1, 0),
    "Please use twisted.conch.insults.helper instead.",
    __name__, "colors")

deprecatedModuleAttribute(
    Version("Twisted", 10, 1, 0),
    "Please use twisted.conch.insults.insults instead.",
    __name__, "client")
