
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

from twisted.python import components


def foo():
    return 2

class X:
    def __init__(self, x):
        self.x = x

    def do(self):
        #print 'X',self.x,'doing!'
        pass


class XComponent(components.Componentized):
    pass

class IX(components.Interface):
    pass

class XA(components.Adapter):
    __implements__ = (IX,)

    def method(self):
        # Kick start :(
        pass

components.registerAdapter(XA, X, IX)
