
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

"""

Twisted Reality: a Text Game Universe

"""

_default = None

# Twisted Imports
from twisted.python import reference

# Sibling Imports
import thing
import reality
import source
import room
import player
import sentence
import container
import error

# Compatibility Section

from thing import Event
from thing import Ambiguous
from thing import Thing

from reality import Reality

from source import SourceRaw
from source import SourceMethod
from source import SourceDict
from source import SourceHash
from source import SourceThing

from room import Room

from player import Player
from player import Intelligence
from player import RemoteIntelligence
from player import LocalIntelligence

from sentence import PseudoSentence
from sentence import _Token
from sentence import _AutoThingSet
from sentence import Sentence

from container import Container
from container import _Contents
from container import Box

from error import RealityException
from error import InappropriateVerb
from error import CantFind
from error import Ambiguity
from error import Failure
from error import NoVerb
from error import NoObject
from error import TooManyObjects
from error import NoExit
from error import NoString
