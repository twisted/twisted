#This is here for backwards-compatibility. 
#It will be removed one version later.

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


