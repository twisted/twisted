# -*- test-case-name: twisted.test.test_jabberjid -*-
#
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

from twisted.internet import reactor, protocol, defer
from twisted.xish import domish, utility

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
