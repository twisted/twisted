
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


# Twisted Imports
from twisted.python import authenticator

class ObjectBrowser:
    def __init__(self, ns):
        self.ns = ns

    def code(self, code):
        try:
            code = compile(code, '$navigator$', 'eval')
            return eval(code, self.ns.__dict__)
        except SyntaxError:
            code = compile(code, '$navigator$', 'exec')
            exec code in self.ns.__dict__

    def move(self, ns):
        self.ns = ns

    def callMeth(self, meth, *args, **kwargs):
        return apply(getattr(self.ns, meth), args, kwargs)

    def getAttrs(self):
        return dir(self.ns)

class SecureObjectBrowser(ObjectBrowser):
    """I am a secure object browser, which only allows you to move to a
    namespace that's contained in your current namespace."""
    def move(self, ns):
        """This method should check that the new namespace is either in your current
        namespace or your last namespace."""
        #This is easy if I require 'ns' to be a string, but that would break
        #compatibility with ObjectBrowser. And if I made ObjectBrowser.move
        #accept a string, how will I make it any more flexible than SecureObjectBrowser
        #(ie, to allow an arbitrary namespace)
        if ns in dir(self.ns):
            self.ns = getattr(self.ns, ns)

    def code(self, code):
        raise authenticator.Unauthorized("You are not allowed to do that in a Secure Object Browser.")
