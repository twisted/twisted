# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
# 

from twisted.cred import portal
from twisted.python import components


class UnixSSHRealm:
    __implements__ = portal.IRealm

    def requestAvatar(self, username, mind, *interfaces):
        return interfaces[0], UnixSSHUser(username), lambda: None


class ISSHUser(components.Interface):
    """A user for an SSH service.  This lets the server get access to things
    like the users uid/gid, their home directory, and their shell.
    """

    def getUserGroupId(self):
        """
        @return: a tuple of (uid, gid) for the user.
        """

    def getHomeDir(self):
        """
        @return: a string containing the path of home directory.
        """

    def getShell(self):
        """
        @return: a string containing the path to the users shell.
        """


class UnixSSHUser:
    __implements__ = ISSHUser

    def __init__(self, username):
        self.username = username
        import pwd
        self.pwdData = pwd.getpwnam(self.username)

    def getUserGroupId(self):
        return self.pwdData[2:4]

    def getHomeDir(self):
        return self.pwdData[5]

    def getShell(self):
        return self.pwdData[6]
