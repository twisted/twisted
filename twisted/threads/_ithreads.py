# -*- test-case-name: twisted.threads.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Interfaces related to therads.
"""

from zope.interface import Interface


class AlreadyQuit(Exception):
    """
    This worker worker is dead and cannot execute more instructions.
    """



class IWorker(Interface):
    """
    A worker that can perform some work concurrently.
    """

    def do(task):  # pragma: nocover
        """
        Perform the given task.

        @param task: a task to call in a thread or other concurrent context.
        @type task: 0-argument callable

        @raise AlreadyQuit: if C{quit} has been called.
        """

    def quit():  # pragma: nocover
        """
        Free any resources associated with this L{IWorker} and cause it to
        reject all future work.

        @raise: L{AlreadyQuit} if this method has already been called.
        """


