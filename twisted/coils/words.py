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

"""Coil plugin for manhole service."""

# Twisted Imports
from twisted.coil import app, coil
from twisted.words import service, ircservice, webwords

# System Imports
import types

# Sibling imports
import web


class WordsConfigurator(app.ServiceConfigurator):

    configurableClass = service.Service
    
    configTypes = {
        'serviceName': types.StringType
        }

    configName = 'Twisted Words Service'

    def __init__(self, instance):
        app.ServiceConfigurator.__init__(self, instance)
        self._setConfigDispensers()
    
    def _setConfigDispensers(self):
        self.configDispensers = [
            ['makeIRCGateway', IRCGatewayConfigurator, "IRC chat gateway to %s" % self.instance.serviceName],
            ['makeWebAccounts', WordsGadgetConfigurator, "Public Words Website for %s" % self.instance.serviceName]
            ]

    def makeWebAccounts(self):
        return webwords.WordsGadget(self.instance)

    def makeIRCGateway(self):
        return ircservice.IRCGateway(self.instance)

    def config_serviceName(self, name):
        raise coil.InvalidConfiguration("You can't change a Service's name.")

def wordsFactory(container, name):
    return service.Service(name, container.app)


class IRCGatewayConfigurator(app.ProtocolFactoryConfigurator):
    
    configurableClass = ircservice.IRCGateway


class WordsGadgetConfigurator(web.ResourceConfigurator):
    
    configurableClass = webwords.WordsGadget


coil.registerConfigurator(WordsConfigurator, wordsFactory)
coil.registerConfigurator(IRCGatewayConfigurator, None)
coil.registerConfigurator(WordsGadgetConfigurator, None)
