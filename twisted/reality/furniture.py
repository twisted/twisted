
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
Furniture support for twisted.reality
"""

#TR imports
import container
import thing
import error

class Chair(container.Container):
    """Chair
    a thing you can sit on
    """
    #Living on the wild side, with this one.
    surface = 1
    # TODO: make this have some stuff that makes it like a chair
    def __init__(self, *args, **kw):
        apply (thing.Thing.__init__,(self,)+args,kw)

    def action_Exit(self, actor):
        "exit (stand from) this chair"
        actor.location = self.location
        actor.broadcastToOne(
            to_subject = ("You stand."),
            to_other =   (actor, ' stands up.')
            )
        return 1
    
    def action_Enter(self, actor):
        "enter (sit on) this chair"
        if actor.location is self:
            actor.hears("You're already sitting there.")
            return 0

        actor.location = self
        actor.broadcastToOne(
            to_subject = ("You sit on ",self.nounPhrase,'.'),
            to_other =   (actor, ' sits on ',self.nounPhrase,'.')
            )
        return 1


    def verb_sit_on(self, sentence):
        return self.action_Enter(sentence.subject)

    verb_sit_in = verb_sit_on
    verb_get_on = verb_sit_on
    verb_get_in = verb_sit_on

    def verb_get_off(self, sentence):
        return self.action_Exit(sentence.subject)

    ambient_stand = verb_get_off
    ambient_go    = verb_get_off
    ambient_exit  = verb_get_off

    def ambient_get(self, sentence):
        """get up|off
        translates to self.action_Exit
        """
        if sentence.directString(None) == "up":
            sentence.shouldOnlyHave('')
            return self.action_Exit(sentence.subject)
        elif (sentence.indirectString("off", None) == ''):
            sentence.shouldOnlyHave("off")
            return self.action_Exit(sentence.subject)
        raise error.InappropriateVerb()

    def set_surface(self, surface):
        assert surface, 'Chairs are always surfaces.'

