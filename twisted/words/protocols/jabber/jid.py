# -*- test-case-name: twisted.words.test.test_jabberjid -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.internet import reactor, protocol, defer
from twisted.xish import domish, utility
import string

class InvalidFormat(Exception):
    pass

def parse(jidstring):
    user = None
    server = None
    resource = None

    # Search for delimiters
    user_sep = jidstring.find("@")
    res_sep  = jidstring.find("/")

    if user_sep == -1:        
        if res_sep == -1:
            # host
            server = jidstring
        else:
            # host/resource
            server = jidstring[0:res_sep]
            resource = jidstring[res_sep + 1:]
    else:
        if res_sep == -1:
            # user@host
            user = jidstring[0:user_sep]
            server = jidstring[user_sep + 1:]
        else:
            if user_sep < res_sep:
                # user@host/resource
                user = jidstring[0:user_sep]
                server = jidstring[user_sep + 1:user_sep + (res_sep - user_sep)]
                resource = jidstring[res_sep + 1:]
            else:
                # server/resource (with an @ in resource)
                server = jidstring[0:res_sep]
                resource = jidstring[res_sep + 1:]

    # Check for misc. invalid cases
    if user and (user.find("@") != -1 or user.find("/") != -1):
        raise InvalidFormat, "Invalid character in username"
    if not server or len(server) == 0:
        raise InvalidFormat, "Server address required."
    if server and (server.find("@") != -1 or server.find("/") != -1):
        raise InvalidFormat, "Invalid character in hostname"

    # Treat empty resource as NULL resource
    if resource and len(resource) == 0:
        resource = None

    # XXX: Do string prep here!

    # Return the tuple
    return (user, server, resource)

__internJIDs = {}

def internJID(str):
    # XXX: Ensure that stringprep'd jids map to same JID
    if str in __internJIDs:
        return __internJIDs[str]
    else:
        j = JID(str)
        __internJIDs[str] = j
        return j

class JID:
    def __init__(self, str = None, tuple = None):
        assert (str or tuple)
        
        if str:
            user, host, res = parse(str)
        else:
            user, host, res = tuple

        self.host = host
        self.user = user
        self.resource = res
            
    def userhost(self):
        if self.user:
            return "%s@%s" % (self.user, self.host)
        else:
            return self.host

    def userhostJID(self):
        if self.resource:
            if "_uhjid" not in self.__dict__:
                self._uhjid = internJID(self.userhost())
            return self._uhjid
        else:
            return self

    def full(self):
        if self.user:
            if self.resource:
                return "%s@%s/%s" % (self.user, self.host, self.resource)
            else:
                return "%s@%s" % (self.user, self.host)
        else:
            if self.resource:
                return "%s/%s" % (self.host, self.resource)
            else:
                return self.host

    def __eq__(self, other):
        return (self.user == other.user and
                self.host == other.host and
                self.resource == other.resource)

    def __ne__(self, other):
        return not (self.user == other.user and
                    self.host == other.host and
                    self.resource == other.resource)
