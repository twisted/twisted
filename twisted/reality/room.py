
# System Imports
import random
import string

# Sibling Imports
import thing
import error

from twisted.python import reflect

class Room(thing.Thing):
    """Room

    A convenience class, setting a few defaults for objects intended
    to be containers which can also contain Players.
    """
    enterable = 1
    hollow = 1

    def containedPhrase(self, observer, other):
        """If something is inside a Room, it is simply `here'.
        """
        return string.capitalize(other.nounPhrase(observer)) + ' is here.'


#And darkness was upon the face of the deep. --Gen
#                                      i. 2.

#theDarkRoom = thing.Thing("Dark Place")(
#    description = "It is pitch black.  You can't see a thing."
#    )

#the following class should not be used, until a bug is fixed.
class DarkRoom(Room):
    """
    This represents a room what is dark and stuff.
    """
    
    lit = 0

    def ambient_(self, sentence):
        if self.lit:
            raise error.InappropriateVerb()
        sentence.subject.hears("It's too dark.")
        return 0

    def ambient_go(self, sentence):
        addtl = ""
        if self.exits:
            exit = random.choice(self.exits)
            room = self.findExit(exit)
            if not reflect.isinst(room, DarkRoom):
                addtl = " and head into the light!"
            sentence.subject.location = room
            sentence.subject.hears("You stumble around blindly...", addtl)
        else:
            sentence.subject.hears("You bash into a wall.")

    def set_lit(self, lit):
        assert lit == 0 or lit == 1, "`lit' must be a boolean"
        # todo; make the room automatically light up when a light source is
        # present.
        if lit != self.lit:
            self.reallySet('lit', lit)
            for thing in self.things:
                thing.reFocus()
            
    def set_surface(self, surface):
        assert 0, "Dark places may not be surfaces."
        
    def focusProxy(self,player):
        if self.lit:
            return self
        else:
            return theDarkRoom
