"""
Twisted Spread Interfaces.

This module is unused so far. It's also undecided whether this module
will remain monolithic.
"""

from twisted.python.components import Interface

class IJellyable(Interface):
    def jellyFor(self, jellier):
        """
        Jelly myself for jellier.
        """

class IUnjellyable(Interface):
    def unjellyFor(self, jellier):
        """
        Unjelly myself for the jellier.
        """
