# -*- test-case-name: twisted.protocols._smb.tests -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Various interfaces for realms, avatars and related objects
"""

from typing import Union, List

from zope.interface import Attribute, Interface


class NoSuchShare(Exception):
    pass


class ISMBServer(Interface):
    """
    A SMB server avatar, contains a number of "shares" (filesystems/printers/
    IPC pipes)
    """

    session_id = Attribute("the assigned int64 session ID")

    def getShare(name: str) -> Union["IFilesystem", "IPipe", "IPrinter"]:
        """
        get a share object by name

        @param name: the share
        @type name: L{str}

        @rtype: instance implementing one of L{IFilesystem}, L{IPrinter}, or
                L{IPipe}
        """

    def listShares() -> List[str]:
        """
        list shares available on the server.
        Note servers are free to have different lists for different users
        and have "silent" shares that don't appear in list

        @rtype: L{list} of L{str}
        """


class IFilesystem(Interface):
    """
    A share representing a filesystem ("disk" in the SMB spec)
    """


class IPrinter(Interface):
    """
    A share representing a printer
    """


class IPipe(Interface):
    """
    A share representing a interprocess communication (IPC) pipe
    """
