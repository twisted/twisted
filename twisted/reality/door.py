
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
Doors for twisted reality.
"""

#TR imports
import thing
import error
import lock

class Door(thing.Thing):
    """Door

    A generally useful Door class for twisted reality."""

    isOpen = 1
    autoclose = 0
    openPhrase = None
    closedPhrase = None
    otherOpenPhrase = None
    otherClosedPhrase = None
    swinger = None


    def install(self, direction):
        """Door.install('direction') -> None
        Install the door """
        self._origin = self.location
        self._direction = direction
        self._destination = self.place.findExit(direction)
        self._reverse = self._destination.findDirection(self._origin)
        self.location = None
        self._origin.grab(self)
        self._destination.grab(self)
        self.component = 1
        self._redescribe()


    def _undescribe(self):
        self._origin.describe(self.name, '')
        self._destination.describe(self.name, '')


    def _redescribe(self):
        if self.isOpen:
            desc = self.openPhrase or [self, " is open."]
            otherDesc = self.otherOpenPhrase or desc
        else:
            desc = self.closedPhrase or [self, " is closed."]
            otherDesc = self.otherClosedPhrase or desc
        self._origin.describe(self.name, desc)
        self._destination.describe(self.name, otherDesc)


    def uninstall(self):
        self.location = self._origin
        self.component = 0
        self._undescribe()


    def set_name(self, name):
        old = self.name
        if old:
            self._undescribe()
        thing.Thing.set_name(self, name)
        if old:
            self._redescribe()


    def verb_open(self, sentence):
        "Open the pod-bay doors, hal."
        perp = sentence.subject()
        if self.isOpen:
            error.Failure("It's already open.")
        self.open(actor = perp)
        perp.hears("You open ",self,'.')


    def verb_close(self, sentence):
        "I'm afraid I can't do that, dave."
        perp = sentence.subject()
        if not self.isOpen:
            error.Failure( "It's already closed." )
        self.close(actor=perp)
        perp.hears("You close ",self,'.')


    def _open(self, actor):
        """Override this to make the door impossible to open manually, or have
        special effects when opening."""


    def _close(self, actor):
        """Override this to make the door impossible to close manually, or have
        special effects when closing."""


    def open(self, actor=None):
        "open the door w/ no side effects or failure"
        self._origin.connectExit(self._direction,  self._destination)
        self._destination.connectExit(self._reverse, self._origin)
        self.isOpen = 1
        self._redescribe()
        if self.autoclose:
            self.swinger = self.reality.later(self._swingShut,
                                              ticks=self.autoclose)
        if actor is not None:
            self._open(actor)

    def _swingShut(self):
        self.swinger = None
        self.close()
        self.broadcast(self, " swings shut.")

    def close(self, actor=None):
        "close the door with no side-effects or failure"
        if self.swinger:
            self.swinger.stop()
        self._origin.disconnectExit(self._direction)
        self._destination.disconnectExit(self._reverse)
        self.isOpen = 0
        self._redescribe()
        if actor is not None:
            self._close(actor)

class AuthorDoor(Door):
    autoclose = 1
    def _open(self, actor):
        if not actor.wizbit:
            error.Failure(self, " just doesn't seem to budge.")


class LockedDoor(Door, lock.LockableMixin):
    def _open(self, actor):
        self.checkLock()

