# -*- test-case-name: twisted._threads.test.test_convenience -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Common functionality used within the implementation of various workers.
"""


from ._ithreads import AlreadyQuit


class Quit:
    """
    A flag representing whether a worker has been quit.

    @ivar isSet: Whether this flag is set.
    @type isSet: L{bool}
    """

    def __init__(self) -> None:
        """
        Create a L{Quit} un-set.
        """
        self.isSet = False

    def set(self) -> None:
        """
        Set the flag if it has not been set.

        @raise AlreadyQuit: If it has been set.
        """
        self.check()
        self.isSet = True

    def check(self) -> None:
        """
        Check if the flag has been set.

        @raise AlreadyQuit: If it has been set.
        """
        if self.isSet:
            raise AlreadyQuit()
