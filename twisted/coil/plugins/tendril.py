# -*- Python -*-
# $Id: tendril.py,v 1.1 2002/04/12 19:02:31 acapnotic Exp $

# Copyright (C) 2001, 2002 Matthew W. Lefkowitz
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

from twisted.coil import coil
from twisted.words import tendril, service
wordsService = service
del service

import types

class TendrilConfigurator(coil.Configurator):

    configName = "IRC Tendril from Twisted Words"
    configurableClass = tendril.Tendril
    
    configTypes = {
        'host': (types.StringType, "Host", "The host this Tendril will connect to."),
        'portno': (types.IntType, "Port", "The port on the host to connect to."),
#        'groupList': types.ListType,
        'nickname': (types.StringType, "Nick",
                     "The nickname this Tendril will sign on to IRC with."),
        'networkSuffix': (types.StringType, "Suffix",
                          "The suffix appended to the names of participants to "
                          "identify them as being on another network.  e.g. @opn"),
#       'perspectiveName': types.StringType,
        'errorGroup': (types.StringType, "Error group",
                       "The group on the Words service to which I will report errors.")
#       'realname': types.StringType,
#       'helptext': 'multiline',
        }

coil.registerConfigurator(TendrilConfigurator)
