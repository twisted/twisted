# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2003 Matthew W. Lefkowitz
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

""" A temporary placeholder for client-capable strports, until we
sufficient use cases get identified """

from twisted.application import strports

def _parseTCPSSL(factory, domain, port):
    """ For the moment, parse TCP or SSL connections the same """
    return (domain, int(port), factory), {}

def _parseUNIX(factory, address):
    return (address, factory), {}


_funcs = { "tcp"  : _parseTCPSSL,
           "unix" : _parseUNIX,
           "ssl"  : _parseTCPSSL }


def parse(description, factory):
    args, kw = strports._parse(description)
    return (args[0].upper(),) + _funcs[args[0]](factory, *args[1:], **kw)

def client(description, factory):
    from twisted.application import internet
    name, args, kw = parse(description, factory)
    return getattr(internet, name + 'Client')(*args, **kw)
