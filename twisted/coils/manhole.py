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
from twisted.manhole import service

# System Imports
import types

class ManholeConfigurator(app.ServiceConfigurator):

    configurableClass = service.Service
    
    configTypes = {
        'serviceName': types.StringType
        }

    configName = 'Twisted Manhole PB Service'

    def config_serviceName(self, name):
        raise coil.InvalidConfiguration("You can't change a Service's name.")

def manholeFactory(container, name):
    return service.Service(name, container.app)

coil.registerConfigurator(ManholeConfigurator, manholeFactory)
