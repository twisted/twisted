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
"""Example of publishing SOAP methods.

Sample usage::

   >>> import SOAPpy
   >>> p = SOAPpy.SOAPProxy('http://localhost:8080/')
   >>> p.add(a=1)
   1
   >>> p.add(a=1, b=3)
   4
   >>> p.echo([1, 2])
   [1, 2]

"""

from twisted.web import soap, server
from twisted.internet import reactor, defer


class Example(soap.SOAPPublisher):
    """Publish two methods, 'add' and 'echo'."""

    def soap_echo(self, x):
        return x

    def soap_add(self, a=0, b=0):
        return a + b
    soap_add.useKeywords = 1

    def soap_deferred(self):
        return defer.succeed(2)


reactor.listenTCP(8080, server.Site(Example()))
reactor.run()

                  
