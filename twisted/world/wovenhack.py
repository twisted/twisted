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

"""
This is not a module.  It is a workaround for the fact that we do not currently
have any way to register an adapter without loading both interfaces and the
adapter, which would entail loading all of woven.

If you are using woven and world together, import this.  Eventually it should
become a no-op.
"""

from twisted.python.components import registerAdapter
from twisted.web.woven.model import ListModel
from twisted.web.woven.interfaces import IModel

from twisted.world.compound import StorableList, IntList, StrList
from twisted.world.util import Backwards

registerAdapter(ListModel, StorableList, IModel)
registerAdapter(ListModel, IntList,      IModel)
registerAdapter(ListModel, StrList,      IModel)
registerAdapter(ListModel, Backwards,    IModel)
