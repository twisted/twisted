
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
Lockable objects
"""

#TR imports
import thing
import error

from twisted.python import reflect

class Key(thing.Thing):
    """ A generic key; something you can unlock stuff with.
    """
    lockTypes = []


class LockableMixin:
    """ Mixable superclass of all lockable objects.

    This is a mixin because it's a feature which can be added to existing Thing
    classes (see door.py for an example of this)
    """
    lockTypes = []
    locked = 0

    def verb_lock(self, sentence):
        "lock <lockable> with key"
        key = sentence.indirectObject("with")
        self.checkKeyMatch(self, key)
        self.lock()


    def verb_unlock(self, sentence):
        "unlock <lockable> with key"
        key = sentence.indirectObject("with")
        self.checkKeyMatch(self, key)
        self.unlock()


    def lock(self):
        "cause self to become locked"
        self.locked = 1


    def unlock(self):
        "cause self to become unlocked"
        self.locked = 0


    def checkLock(self):
        "raise an appropriate exception if this is locked."
        if self.locked:
            error.Failure(self," is locked.")


    def checkKeyMatch(self, key):
        """ Check to see if the given key matches this object's lock.

        Raise a error.Failure if it does not.  Override this method to
        implement different key-matching mechanisms; by default, I will check
        that one of the key's lockTypes is in my list of lockTypes.
        """
        if not reflect.isinst(key, Key):
            error.Failure("That's not a key.")
        for type in key.lockTypes:
            if type in self.lockTypes:
                return
        error.Failure(key, " doesn't seem to fit.")


class Lockable(thing.Thing, LockableMixin):
    "A convenience class that mixes in the Lockable functionality."
