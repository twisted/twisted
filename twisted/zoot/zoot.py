# Twisted, the Framework of Your Internet
# Copyright (C) 2002 Bryce "Zooko" Wilcox-O'Hearn
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

"""Zooko's implementation of Gnutella."""

class Zoot:
    def __init__(self, app):
        self.twistedapp = app
        self.host = None # As soon as a connection is made, this will get filled in.  Future versions of Twisted may provide a nicer way to get this information, even before the first connection is established.

    def setHost(self, host):
        assert (self.host is None) or (self.host == host)
        self.host = host

    def getHost(self):
        return self.host
