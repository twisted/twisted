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

"""Coil plugin for words service."""

# Twisted Imports
from twisted.protocols import protocol
from twisted.internet.interfaces import IConnector
from twisted.coil import coil
from twisted.words import service, ircservice, tendril, webwords
from twisted.web import resource

# System Imports
import types

class WordsConfigurator(coil.Configurator):

    configurableClass = service.Service

    configTypes = {
        'serviceName': [types.StringType, "Service Name", ""]
        }

    configName = 'Twisted Words Service'

    def __init__(self, instance):
        coil.Configurator.__init__(self, instance)

    def configDispensers(self):
        return [
            ['makeIRCGateway', protocol.IFactory,
             "IRC chat gateway to %s" % self.instance.serviceName],
            ['makeWebAccounts', resource.IResource,
             "Public Words Website for %s" % self.instance.serviceName],
            ['makeTendril', IConnector,
             "Tendril to IRC from %s" % (self.instance.serviceName,)]
            ]

    def makeWebAccounts(self):
        return webwords.WordsGadget(self.instance)

    def makeIRCGateway(self):
        return ircservice.IRCGateway(self.instance)

    def makeTendril(self):
        return tendril.TendrilFactory(self)

    def config_serviceName(self, name):
        raise coil.InvalidConfiguration("You can't change a Service's name.")

def wordsFactory(container, name):
    return service.Service(name, container.app)

coil.registerConfigurator(WordsConfigurator, wordsFactory)
