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

"""Coil plugin for SOCKSv4 proxy."""

# Twisted Imports
from twisted.coil import coil
from twisted.protocols import socks

# System Imports
import types


class SOCKSConfigurator(coil.Configurator):

    configurableClass = socks.SOCKSv4Factory
    
    configTypes = {
        'logging': [types.StringType, "Logfile", "Path to log file."]
        }

    configName = 'SOCKSv4 Proxy'


def factory(container, name):
    return socks.SOCKSv4Factory(None)


coil.registerConfigurator(SOCKSConfigurator, factory)
