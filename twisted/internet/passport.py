
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

"""Authorization & authentication in Twisted.

This module is for backwards compatability purposes only. Use twisted.cred
instead.
"""

# System Imports
import md5
import random
import warnings
warnings.warn('twisted.internet.passport now obsolete, use twisted.cred')

from twisted.cred.service import Service
from twisted.cred.perspective import Perspective
from twisted.cred.identity import Identity
from twisted.cred.util import Unauthorized
from twisted.cred.util import respond
from twisted.cred.util import challenge

from twisted.cred.authorizer import Authorizer
from twisted.cred.authorizer import DefaultAuthorizer
