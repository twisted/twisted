
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

"""Basic twisted.reality simulation classes.
"""

# System Imports.
import types
import copy
import string

import cStringIO
StringIO = cStringIO
del cStringIO

# Sibling Imports
import error
import sentence
import source

# Twisted Imports
from twisted.python import threadable, observable, reflect
from twisted.protocols import protocol
from twisted.persisted import styles
# backward compatibility
import twisted.reality

#the default reality which things will use.
_default = None

class Event(reflect.Settable):
    """Event()
    Essentially a dicitonary -- this encapsulates the idea of an event
    which can be published."""

class Ambiguous:
    """A dictionary which may contain ambiguous entries.
    """
    def __init__(self):
        """Initialize.
        """
        self.data = {}

    def put(self, key,value):
        """Put a value into me with the given key.
        If I already have a reference to that key, further retrievals will be ambiguous.
        """
        if type(key)==types.StringType:
            key = string.lower(key)
        try:
            x = self.data[key]
            x.append(value)
        except:
            self.data[key] = [value]

        self.data = self.data

    def get(self,key):
        """Retrieve a value.
        
        This always returns a list; if it is empty, then I do not contain the
        given key.  If it has one entry, then the retrieval is not ambiguous.
        If it has more than one, the retrieval is ambiguous.
        """
        if type(key)==types.StringType:
            key = string.lower(key)
        x = self.data.get(key, [])
        return x

    def remove(self,key,value):
        """Remove one value for a particular key.
        If there are multiple entries under this key, disambiguate.  Otherwise,
        remove this key entirely.
        """
        if type(key)==types.StringType:
            key = string.lower(key)
        x = self.data[key]
        x.remove(value)
        if len(x)==0:
            del self.data[key]
        self.data = self.data

class Thing(observable.Publisher,
            observable.Subscriber,
            reflect.Settable):
    """Thing(name[,reality])

    name: a string, which will be both the unique keyed name of this
    object, and the displayed name.

    reality: an instance of a twisted.reality.Reality, or None.  If it
    is unspecified, the reality of this object will be set to the
    value of the module-global '_default'.
    """

    # This is a list of synchronized method names.
    synchronized = [
        'execute',
        'set_location',
        'set_name',
        'set_displayName',
        'set_reality',
        ]

    # Version: this is independant of the twisted reality version; it
    # is important so that the pickles can be re-read and frobbed as
    # necessary
    __version = 4
    # Most rooms aren't doors; they don't "go" anywhere.
    destination = None
    # most things are opaque.
    transparent = 0

    # most things aren't containers; they don't have an "inside", to
    # speak of.  This isn't a hard and fast rule, since it's useful to
    # be able to combine objects in this relationship, but this is a
    # useful hint.
    hollow=0

    # See the "room" classes below for more details.
    enterable = 0
    # what 'reality' this belongs to.
    reality = None
    # whatever this player last "talked about"; it will be used when
    # they refer to 'it'
    antecedent = None
    # if you're performing actions, are you an administrator?
    wizbit=0

    def __init__(self, name, reality=''):
        """Thing(name [, reality])

        Initialize a Thing.
        """
        # State setup.
        self.__index = Ambiguous()
        self.__version = self.__version
        self.__description = {"__MAIN__":""}
        self.__exits = {}
        self.__synonyms = []
        self._containers = []
        self._contained = []

        # More state setup, these with constraints.
        self.name = str(name)
        if reality == '':
            #this is for backwards-compatibility: check both the package
            #_default and the local _default. Delete this check for 0.9.1
            if _default is not None:
                self.reality = _default
            elif twisted.reality._default is not None:
                self.reality = twisted.reality._default
            else:
                self.reality = None #this could happen before, so it still can.
        else:
            self.reality = reality

    def set_reality(self, reality):
        if self.reality is reality:
            return
        if self.reality is not None:
            self.reality._removeThing(self)
        if reality is not None:
            reality._addThing(self)
        self.reallySet('reality',reality)
        for thing in self.things:
            thing.reality = reality


    # The 'true name' string of this object.
    name=None
    # The name of this object that gets displayed when players look at
    # it.
    displayName=None

    def set_name(self, name):
        """Thing.name = name

        Set the name of this Thing.
        """
        assert type(name)==types.StringType, "Name must be a string."
        if name == self.name:
            return
        if self.name is not None:
            self.removeSynonym(self.name)
        oldname=self.name
        self.reallySet('name',name)
        if self.reality is not None:
            self.reality._updateName(self,oldname,name)
        self.addSynonym(name)
        if not self.displayName:
            self.publish('name',self)

    def set_displayName(self, name):
        """Thing.displayName = name
        Change the displayed name of this thing.  """
        if type(name)==types.StringType:
            self.addSynonym(name)
        if self.displayName and type(self.displayName) == types.StringType:
            self.removeSynonym(self.displayName)
        self.reallySet('displayName',name)
        self.publish('name',self)

    def on_name(self, data):
        """Thing.on_name(data) -> None
        Called when 'name' is published, to upate the visible name of
        this object in all of its containers.
        """
        self.__changeVisibility(1)

    ### Perspectives

    article=None

    def indefiniteArticle(self, observer):
        """Thing.indefiniteArticle(observer) -> 'a ' or 'an '

        Utility function which figures out the appropriate indefinite
        article to display based to the given observer based on the
        short name displayed to that observer.  """
        name=self.shortName(observer)
        if string.lower(name[0]) in ('a','e','i','o','u'):
            return 'an '
        else: return 'a '

    def definiteArticle(self, observer):
        """Thing.definiteArticle(observer) -> 'the '

        Returns 'the' or nothing, depending on whether or not it would be
        appropriate to label this object with a definite article.  """
        return 'the '

    aan=indefiniteArticle
    the=definiteArticle

    unique=0


    def article(self, observer):
        """Thing.article(observer) -> 'a ' or 'an ' or 'the '

        Determine the article of an object.
        """
        return self.definiteArticle(observer)

    def capNounPhrase(self,observer):
        "The capitalized version of this object's noun phrase."
        return string.capitalize(self.nounPhrase(observer))

    def nounPhrase(self, observer):
        """Thing.nounPhrase(observer) -> string
        A brief phrase describing this object, such as 'the blue fish' or
        'a bicycle'."""
        return self.article(observer)+self.shortName(observer)


    contained_preposition = "on"

    def containedPhrase(self, observer, containedThing):
        """Thing.containedPhrase(observer, containedThing) -> 'A containedThing is in the self'
        
        This returns a phrase which relates self's relationship to
        containedThing.  It's used to calculate containedThing's presentPhrase
        to the given observer. """

        return "%s is %s %s." % (string.capitalize(containedThing.nounPhrase(observer)),
                                self.contained_preposition,
                                self.nounPhrase(observer))
                
    def presentPhrase(self, observer):
        """Thing.presentPhrase(observer) -> 'A self is in the box', 'Bob is holding the self'
        
        A brief phrase describing the presence and status of this object, such
        as 'A fish is here' or 'A bicycle is leaning against the rack.'.  """
        
        location = self.location
        if location is None:
            return "%s%s is nowhere" % self.indefiniteArticle(observer)
        
        return location.containedPhrase(observer, self)


    def shortName(self, observer):
        """Thing.shortName(observer) -> 'blue box'
        The unadorned name of this object, as it appears to the specified
        observer.  """
        
        displayName = self.displayName
        if displayName:
            if callable(displayName):
                return displayName(observer)
            else:
                return displayName
        else:
            return self.name

    def get_things(self):
        "Thing.things -> a list of the contents of this object."
        return tuple(self._contained)

    def get_allThings(self):
        """Thing.allThings -> a complete list of contents for this object.
        
        This is the list of contents of an object, plus any objects in surfaces
        which are visible from it.
        """
        stuff = {}
        for thing in self.things:
            if not thing.component:
                stuff[thing] = None
            if thing.surface:
                for thing2 in thing.allThings:
                    stuff[thing2] = None
        return stuff.keys()

    def getVisibleThings(self, observer):
        """Thing.getVisibleThings(observer) -> list of Things
        This function will return all things which this thing contains (obvious
        or not) which are visible to the player"""
        # of course, invisibility isn't implemented yet.
        return self.allThings
    
    def getThings(self, observer):
        """Thing.getThings(observer) -> list of Things
        This function filters out the objects which are not obvious to the
        observer.  """
        things = []
        for thing in self.allThings:
            if thing.isObviousTo(observer):
                things.append(thing)
        
        return things

    gender='n'

    def __gender(self, observer):
        """(private) Thing.__gender(observer) -> 'm', 'f' or 'n'
        what gender this object appears to be to the given observer.
        """
        if callable(self.gender):
            return self.gender(observer)
        else:
            return self.gender

    def himHer(self, observer):
        """Thing.himHer(observer) -> 'him', 'her', or 'it'

        returns 'him' 'her' or 'it' depending on the perceived gender
        of this object. """
        return {'m':'him','f':'her','n':'it'}[self.__gender(observer)]

    def capHimHer(self, observer):
        """Thing.capHimHer(observer) 'Him', 'Her', or 'It'

        see Thing.himHer()"""
        return string.capitalize(self.himHer(observer))

    def hisHer(self, observer):
        """Thing.hisHer(observer) -> 'his', 'her', or 'its'

        returns 'his', 'her', or 'its', depending on the perceived
        gender of this object """
        return {'m':'his','f':'her','n':'its'}[self.__gender(observer)]

    def capHisHer(self, observer):
        """Thing.capHisHer(observer) 'His', 'Her', or 'Its'

        see Thing.hisHer()"""
        return string.capitalize(self.hisHer(observer))

    def heShe(self, observer):
        """Thing.heShe(observer) -> 'he', 'she', or 'it'

        returns 'he', 'she', or 'it', depending on the perceived
        gender of this object """
        return {'m':'he','f':'she','n':'it'}[self.__gender(observer)]

    def capHeShe(self, observer):
        """Thing.capHeShe(observer) -> 'his', 'her', or 'its'

        returns 'he', 'she', or 'it', depending on the perceived
        gender of this object """
        return string.capitalize(self.heShe(observer))

    def format(self, persplist):
        """Thing.format(list of things and strings) -> string

        Renders a list which represents a phrase based on this object
        as the observer.  For example:

        x = Thing('mop')
        y = Player('bob')
        print y.format(['You dance with ',mop.nounPhrase,'.'])

        would yeild: 'You dance with the mop.' """

        if type(persplist)==types.StringType:
            return persplist
        elif type(persplist)==types.NoneType:
            return ""
        elif callable(persplist):
            return persplist(self)
        else:
            persplist = list(persplist)
        if persplist and reflect.isinst(persplist[0],Thing):
            persplist[0] = persplist[0].capNounPhrase
        x = StringIO.StringIO()
        for i in persplist:
            if reflect.isinst(i,Thing):
                val=i.nounPhrase(self)
            elif callable(i):
                # this could be one of the things we just defined (wrt
                # gender) or it could be an observable.Dynamic
                val=i(self)
            else:
                val=str(i)
            x.write(val)
        return x.getvalue()

    def hears(self, *args):
        """Thing.hears(*list of perceptibles) -> None

        Causes this Player to hear this list as formatted by
        self.format()
        """
        string=self.format(args)
        if self._hasIntelligence():
            self.intelligence.seeEvent(string)

    def broadcast(self, *evt):
        """Thing.broadcast(...) -> None
        Display some event text to all who can see this item."""
        for container in self._containers:
            apply(container.allHear, evt)

    def broadcastToPair(self, target,
                        to_subject, to_target, to_other):
        """Thing.broadcastToPair(target, to_subject,
                                 to_target, to_other) -> None

        Broadcast some event text to all who can see this actor and
        the specified target (in the style of pairHears).  Prefer this
        form, as it will deal with the actor and target having
        multiple and/or separate locations."""
        contList = self._containers
        if target is not None:
            contList = contList + target._containers
        contUniq = {}
        for container in contList:
            contUniq[container] = 1
        for container in contUniq.keys():
            container.pairHears(self, target, to_subject, to_target, to_other)


    def broadcastToOne(self, to_subject, to_other):
        """Thing.broadcastToOne(to_subject, to_other) -> None

        Broadcast some event text to all who can see this subject (in the style
        of oneHears).  Prefer this form, as it will deal with the actor and
        target having multiple and/or separate locations.
        """
        
        self.broadcastToPair(target=None,
                             to_subject=to_subject,
                             to_target=(),
                             to_other=to_other)
                       


    def pairHears(self,
                  subject,
                  target,
                  to_subject,
                  to_target,
                  to_other):
        """Thing.pairHears(self, subject, target, to_subject,
                           to_target, to_other)

        Sends a message to a list of 3 parties - an initiator of an
        action, a target of that action, and everyone else observing
        that action.  The messages to each party may be a single
        formattable object, or a list or tuple of such objects, which
        will be formatted by the 'hears' method on each observer.

        Example:
        room.pairHears(sentence.subject, target,
        to_subject=("You wave to ",target," and ",target.heShe," nods."),
        to_target= (sentence.subject," waves to you, and you nod."),
        to_other=(sentence.subject," waves to ",target," and ",target.heShe," nods.")
        )

        In this example, when bob executes "wave to jethro", the
        effect is:

        BOB hears:           "You wave to Jethro, and he nods."
        JETHRO hears:        "Bob waves to you, and you nod."
        EVERYONE ELSE hears: "Bob waves to Jethro, and he nods."

        This sort of interaction is useful almost anywhere a verb
        enables a player to take action on another player.
        """

        if type(to_subject) not in (types.TupleType,types.ListType):
            to_subject = (to_subject,)
        if type(to_target)  not in (types.TupleType,types.ListType):
            to_target  = (to_target,)
        if type(to_other)   not in (types.TupleType,types.ListType):
            to_other   = (to_other,)
        if subject is not None:
            apply(subject.hears,to_subject)
        if target is not None:
            apply(target.hears,to_target)

        map(lambda x, to_other=to_other: apply(x.hears,to_other),
            filter(lambda x, subject=subject, target=target: x not in (subject,target),
                   self.things)
            )

    def allHear(self, *args):
        """Thing.allHear(*list to be formatted)

        Sends a message to everyone in the room.  This method
        should be used when there isn't a specific Player who is the
        source of the message. (an example would be Gate disappearing).

        Its arguments should be in the same form as 'hear'

        Examples: room.allHear(disembodied_voice," says 'hello'.")
                  room.allHear("Nothing happens here.")
        """
        for thing in self.things:
            apply(thing.hears,args)

    def oneHears(self, subject, to_subject, to_other):
        """Thing.oneHears(subject, to_subject, to_other)

        Sends a one to everyone in the room except one player, to whom
        a different message is sent.  The arguments may be a valid
        formattable object (a String, Thing, Dynamic, or Exception) or
        a list or tuple of formattable objects.

        Example: room.oneHears(sentence.subject,
                                to_subject=("You pull on ",knob,
                                            " but it just sits there.")
                                to_other=(sentence.subject," pulls on ",knob,
                                          " and looks rather foolish."))
        """
        if type(to_subject) not in (types.TupleType,types.ListType):
            to_subject = (to_subject,)
        if type(to_other)   not in (types.TupleType,types.ListType):
            to_other   = (to_other,)

        apply(subject.hears, to_subject)
        for thing in self.things:
            if thing is not subject:
                apply(thing.hears, to_other)

    def _hasIntelligence(self):
        return hasattr(self,"intelligence")

    def del_focus(self):
        """del Thing.focus
        stop observing the object that you're focused on."""
        self.reallyDel('focus')
        if self._hasIntelligence():
            self.intelligence.seeNoItems()
            self.intelligence.seeNoDescriptions()
            self.intelligence.seeNoExits()

    def isObviousTo(self, player):
        """Thing.isObviousTo(player)
        This returns whether or not this item should appear in
        inventory listings.  It's different from "visible" because a
        player presumably wouldn't be able to interact very well with
        invisible objects, but certain objects that are part of the
        room's description may be non-obvious."""
        return (not self.component) and (self is not player)


    def _fullUpdateTo(self,player):
        """(internal) Thing._fullUpdateTo(player) -> None
        Update a player's UI regarding the state of this object."""
        i = player.intelligence
        i.seeName(self.shortName(player))
        for key, value in self.__description.items():
            i.seeDescription(key,self.format(value))
        for direction, exit in self.__exits.items():
            i.seeExit(direction,exit)
        for item in self.getThings(player):
            i.seeItem(item, item.presentPhrase(player))

    def descriptionTo(self, player):
        return string.join(map(player.format,self.__description.values()))

    def set_focus(self, focus):
        """Thing.focus = newfocus
        begin observing another object"""
        assert focus is None or reflect.isinst(focus, Thing),\
               "Focus must be a Thing, or None"
        if hasattr(self,'focus'):
            del self.focus
        self.reallySet('focus',focus)
        if self._hasIntelligence() and reflect.isinst(focus,Thing):
            focus._fullUpdateTo(self)

    def when_focus_description(self, focus, channel,
                               (key, value)):
        if self._hasIntelligence():
            if value:
                self.intelligence.seeDescription(key, self.format(value))
            else:
                self.intelligence.dontSeeDescription(key)

    def when_focus_name(self,focus,channel,changed):
        "Hook called when our focus publishes a new name."
        if self._hasIntelligence():
            if focus is changed:
                self.intelligence.seeName(changed.shortName(self))
            else:
                if changed is not self:
                    self.intelligence.seeItem(changed,
                                              changed.presentPhrase(self))

    def when_focus_exit(self, focus, channel, exit):
        "Hook called when exits are added to or removed from my focus"
        if self._hasIntelligence():
            if exit.destination:
                self.intelligence.seeExit(exit.direction,exit.destination)
            else:
                self.intelligence.dontSeeExit(exit.direction)

    def when_focus_enter(self,focus,channel,movementEvent):
        "Hook called when things enter my focus"
        if self._hasIntelligence():
            mover = movementEvent.mover
            if mover.isObviousTo(self):
                self.intelligence.seeItem(mover, mover.presentPhrase(self))

    def when_focus_leave(self,focus,channel,movementEvent):
        "Hook called when things leave my focus"
        if self._hasIntelligence():
            mover = movementEvent.mover
            if mover.isObviousTo(self):
                self.intelligence.dontSeeItem(mover)

    def del_intelligence(self):
        """del Thing.intelligence
        remove the user-interface component of this Thing"""
        del self.intelligence.thing
        self.reallyDel('intelligence')

    def set_intelligence(self, intelligence):
        """Thing.intelligence = intelligence
        Change the user-interface component currently governing this
        Thing.  NOTE: this is poorly named and likely to change in the
        near future.  """
        try:   del self.intelligence
        except AttributeError: pass
        self.reallySet('intelligence',intelligence)
        self.intelligence.thing = self
        self.reFocus()

    ### Client Interaction

    def request(self, question, default, callback):
        """Thing.request(question,default,callback)

        question: a question you want to ask the player

        default: a default response you supply
        callback: An object with two methods --    
          ok: a callable object that takes a single string argument.
              This will be called if the user sends back a response.

          cancel: this will be called if the user performs an action 
                  that indicates they will not be sending a response.
                  There is no guarantee that this will ever be called
                  in the event of a disconnection.  (It SHOULD be
                  garbage collected for sure, but garbage collection
                  is tricky. ^_^) """
        
        self.intelligence.request(question,default,callback)
        
    def execute(self, sentencestring):
        """Thing.execute(string)
        Execute a string as if this player typed it at a prompt.
        """
        try:
            s = sentence.Sentence(sentencestring,self)
            return s.run()
        except error.RealityException, re:
            self.hears(re.format(self))
            return re
        except AssertionError, ae:
            self.hears(ae.args[0])

    def userInput(self, sentencestring):
        """Thing.userInput(sentencestring)
        This method insulates self.execute from Gloop.
        """
        try:
            x = self.execute(sentencestring)
            if type(x) == types.StringType:
                return x
        except:
            import traceback
            sio = StringIO.StringIO()
            traceback.print_exc(file=sio)
            print "while executing", repr(sentencestring)
            print sio.getvalue()
            self.hears(sio.getvalue())
        return None


    ambient_ = None

    def getVerb(self, verbstring, preposition):
        """Thing.getVerb(verbName, preposition) -> callable or None

        Return the appropriate method to call for the given verb.  Verbs are
        code which is attached to instances by writing methods of the form
        verb_<verbname>_<preposition>(self, sentence), or verb_<verbname>(self,
        sentence).

        For example:

        class Mop(Thing):
          def verb_dance_with(self, sentence):
            self.hears('You dance with ',self,'.')

        defines the class 'mop', which I can dance with, and

        class Flower(Thing):
          def verb_smell(self, sentence):
            self.hears(self, ' smells nice.')

        defines a flower that I can smell."""
        
        if preposition:
            return getattr(self, "verb_%s_%s"%(verbstring,preposition), None)
        else:
            return getattr(self, "verb_%s"%verbstring, None)


    def getAmbient(self, verbstring):
        """Thing.getAmbient(self, verbstring) -> callable or None

        Get an ambient verb (one which is present on a location, rather than an
        object in the sentence).  These are resolved both on the player's
        locations (in order from outermost to innermost).

        For example:
        
        class ComfyChair(twisted.library.furniture.Chair):
          def ambient_go(self, sentence):
            self.hears('But you\'re so comfy!')

        is a particularly nasty thing to sit in.
        """
        return getattr(self, "ambient_%s" % verbstring, self.ambient_)


    def getAbility(self, verbstring):
        """Thing.getAbility(verbName) callable or None

        Return the appropriate method to call for the given ability.  Abilities
        are intrinsic verbs which a player can execute -- they are methods of 
        the form ability_<name>(self, sentence) (similiar to verbs).
        """
        
        return getattr(self, 'ability_%s' % verbstring, None)
    
    # place = None
    location = None

    def set_place(self, place):
        assert 0, "You may not set the place of an object manually."

    def set_location(self, location):
        """Thing.location = location
        Change something's physical location.
        Publishes:
          * Argument: Event w/ 'source', 'destination' and 'mover' attributes
          * to self: 'move'
          * to destination: 'enter'
          * to all source locations: 'leave'
        """
        oldlocation = self.location
        movement = Event(source      = oldlocation,
                         destination = location,
                         mover       = self)
        if location is not None:
            self.reality = location.reality
        if oldlocation is not None:
            oldlocation.toss(self, destination=location)
            self.reallyDel('location')
        if location is not None:
            self.publish('move',movement)
            self.reallySet('location', location)
            location.grab(self, source=oldlocation)
        self.reFocus()

    def reFocus(self):
        """
        re-set this player's focus.
        """
        if self._hasIntelligence():
            self.focus = self.place.focusProxy(self)
        
    def focusProxy(self, player):
        """This is a hook for darkness and the like; it indicates what your
        focus will default to when you enter a location.
        """
        return self


    def del_location(self):
        """del Thing.location
        Location an object at 'nowhere'."""
        self.location = None

    def move(self, destination, actor):
        """Thing.move(destination, actor) -> None

        Attempts to move an object to a destination by an Actor; if
        this object is immovable by this actor (to this destination)
        for some reason, this will raise a Failure. """

        if self.component:
            error.Failure("It's stuck.")
        self.location = destination

    # special bits (THE FEWER OF THESE THE BETTER!!!)

    # Special bits change the way that objects are managed, so if the
    # code managing them is buggy, the map will become corrupt.  This
    # is the source of many of the problems that arose with TR 1.

    component = 0
    surface = 0

    # To begin with, let's say we'll do transparency without any
    # special bits.  Transparent objects should be able to do things
    # quite easily by subclassing and overriding grab, toss, and find.

    def set_surface(self, surf):
        """Thing.surface = 1 or 0

        This sets (or unsets) the 'surface' boolean.  A 'surface' object
        broadcasts its list of contents (including components) to the
        room that it is found in.
        """
        assert surf == 1 or surf == 0, '"Surface" should be a boolean.'
        oldSurface = self.surface
        self.reallySet('surface',surf)
        if surf == self.surface:
            return
        # get a list of all the containers who might want to know about this
        if surf:
            channel = 'enter'
        else:
            channel = 'leave'
            
        allContainers = self.allContainers
        
        for thing in self.allThings:
            event = Event(
                source = self,
                destination = self,
                mover = thing,
                simulated = 1)
            for container in allContainers:
                container.publish(channel, event)

    def del_surface(self):
        """del Thing.surface
        Set the 'surface' attribute of this thing back to whatever its
        class default is.
        """
        self.set_surface(self.__class__.surface)
        self.reallyDel('surface')

    def set_locations(self):
        "Thing.locations = ... Raise an AttributeError."
        raise AttributeError("'locations' attribute not settable")

    def get_locations(self):
        """Thing.locations
        This is the list of locations that can "see" this object.
        Starting with the object's direct location, it continues up
        until the object's "place"; so it will collect all locations
        up the containment heirarchy until the object's "top level"
        location, i.e. the first one which isn't a surface.
        """
        locations = []
        location = self.location
        while reflect.isinst(location, Thing):
            locations.append(location)
            if not location.surface:
                break
            location = location.location
        return tuple(locations)


    def set_component(self,comp):
        """Thing.component = boolean
        This sets the 'component' boolean.  A 'component' object is a
        part of the object which contains it, and cannot be moved or
        altered independantly.
        """
        assert comp == 1 or comp == 0, '"Component" should be a boolean.'
        if comp == self.component:
            return

        if comp:
            self.__changeVisibility(not comp)
            self.reallySet('component',1)
        else:
            self.reallySet('component',0)
            self.__changeVisibility(not comp)

    def get_place(self):
        """Thing.place -> Thing or None
        This returns the `place' of an object.
        """
        if not self.locations:
            return None
        return self.locations[-1]
    
    def __resetPlace(self):
        """(private) Thing.__resetPlace() -> None

        Make sure an object's 'place' attribute is properly set. """
        self.reallySet("place", self.locations[-1])


    def __changeVisibility(self, bool):
        """(private) Thing.__changeVisibility(obj, bool)
        fake a movement event to tell an object's locations that
        something's name or visibility state changed """
        if bool:
            channel = 'enter'
            source = None
        else:
            channel = 'leave'
            destination = None
        for container in self.allContainers:
            if bool:
                destination = container
            else:
                source = container
            container.publish(channel,
                              Event(source=source,
                                    destination=destination,
                                    mover=self,
                                    simulated=1))


    def get_allContainers(self):
        cont = []
        for container in self.containers:
            cont.append(container)
            if container.surface:
                for container2 in container.allContainers:
                    cont.append(container2)
        return tuple(cont)
    
    def get_containers(self):
        """Thing.containers -> a list of objects that contain this
        This is a list of objects which directly contain this object.
        """
        return tuple(self._containers)

    def set_containers(self, newContainers):
        oldContainers = copy.copy(self._containers)
        for container in newContainers:
            if container not in oldContainers:
                container.grab( self )

        for container in oldContainers:
            if ((container not in newContainers)
                and (container is not self.location)):
                container.toss( self )

    def _publishEnterOrLeave(self, channel,
                             mover, source, destination,
                             simulated=0):
        "(private): common event sending code"
        if not simulated:
            events = [Event(source = source,
                            destination = destination,
                            mover = mover,
                            simulated = simulated)]
        else:
            events = []
        if mover.surface or simulated:
            for subthing in mover.allThings:
                events.append(Event(
                    source = source,
                    destination = destination,
                    mover = subthing,
                    simulated = simulated))
        for event in events:
            self.publish(channel, event)
        if self.surface:
            for container in self.allContainers:
                for event in events:
                    container.publish(channel, event)

    def grab(self, thing, source=None):
        """Location.grab(thing[,destination]) -> None

        Add thing to location's list of searchable children. (TODO:
        doc this better) """
        assert not thing in self._contained,\
               "Duplicate grab: %s already has %s." % (str(self), str(thing))
        
        thing._containers.append(self)
        self._contained.append(thing)
        location = self.location
        for i in thing.synonyms:
            self.__addref(i,thing)
        self._publishEnterOrLeave('enter',
                                  mover=thing,
                                  source=source,
                                  destination=self)


    def toss(self, thing, destination=None):
        """Container.toss(thing[, destination])

        Remove an object from a container and sends the appropriate
        events.  (Optionally, publish the given source with 'leave'
        instead of constructing one.)"""
        
        assert thing in self._contained,\
               "can't toss %s from %s" % (thing, self)
        
        self._publishEnterOrLeave('leave',
                                  mover=thing,
                                  source=self,
                                  destination=destination)
        for i in thing.synonyms:
            self.__remref(i,thing)
        thing._containers.remove(self)
        self._contained.remove(thing)

    def addSynonym(self, synonym):
        """Thing.addSynonym(synonym)
        Adds a new synonym that this object can be referred to as"""
        synonym = string.lower(synonym)
        if synonym in self.synonyms:
            return
        for container in self._containers:
            container.__addref(synonym,self)
        self.__synonyms.append(synonym)
        self.changed = 1

    def removeSynonym(self, synonym):
        """Thing.removeSynonym(synonym)
        Removes a synonym from this object, so that it can no longer
        be referred to in that way."""
        synonymn = string.lower(synonym)
        if (synonym == self.name) or (not synonym in self.__synonyms):
            return
        for container in self._containers:
            container.__remref(synonym,self)
        self.__synonyms.remove(synonym)
        self.changed = 1

    def set_synonyms(self, syns):
        """Thing.synonyms = [list of synonyms]
        Add a list of synonyms at once."""
        for i in syns:
            self.addSynonym(i)

    def get_synonyms(self):
        return tuple(self.__synonyms)

    def get_exits(self):
        return tuple(self.__exits.keys())

    def __addref(self,k,t):
        self.__index.put(k,t)

    def __remref(self,k,t):
        self.__index.remove(k,t)

    def __repr__(self):
        return "<%s '%s'>" % (self.__class__.__name__,
                              self.name)


    def destroy(self):
        """Thing.destroy() -> None: Destroy this object.
        
        If you write code which maintains a reference to a Thing, you probably
        need to register a subscriber method so that you can drop that Thing
        reference when it's destroyed.
        
        Publishes:
            * 'destroy' to self: Event with 'destroyed' attribute.
        """
        self.component = 0
        # First, make sure I don't have a container any more.
        self.location = None
        # then, tell everyone who cares I'm about to go away.
        self.publish('destroy', Event(destroyed=self))
        for thing in self.things:
            if thing.location is self:
                thing.location = None
        for thing in self._contained:
            self.toss(thing)
        for l in self.__index.data.values():
            for x in l:
                print self, x, x.location
        # Then, take all of my non-component stuff and kill it.
        self.reality._removeThing(self)

    ### Searching

    def _find(self, name):
        """Thing._find(name) -> list of Things
        Search the contents of this Thing for a Thing known by the
        synonym given.  Returns a list of all possible results.
        """
        stuff = {}
        for item in self.__index.get(name):
            stuff[item] = None
        for loc in self.things:
            if loc.surface:
                for item in loc._find(name):
                    stuff[item] = None
        return stuff.keys()

    def find(self, name):
        """Thing.find(name) -> Thing
        
        Search the contents of this Thing for a Thing known by the synonym
        given.  If there is only one result, return it; otherwise, raise an
        Ambiguity describing the failure."""
        lst = self._find(name)
        ll = len(lst)
        if ll == 1:
            return lst[0]
        elif ll == 0:
            raise error.CantFind(name)
        elif ll > 1:
            raise error.Ambiguity(name, lst)

    def locate(self, word):
        """Thing.locate -> Thing
        Tell this Player to locate a Thing by a synonym it may be
        known by.  """
        # In order that some objects may be garuanteed not to be found by the
        # parser, name them with a $ as the first character.
        if word and word[0] == '$':
            raise error.CantFind(word)
        elif word == 'here':
            return self.location
        elif word == 'me':
            return self
        elif word == 'this':
            return self.focus
        elif word in ('him','her','it'):
            if self.antecedent:
                return self.antecedent
            
        stuff = {}
        for loc in self, self.location, self.focus:
            if loc:
                for found in loc._find(word):
                    stuff[found] = None
                    
        stuff = stuff.keys()
        ls = len(stuff)
        if ls == 1:
            return stuff[0]
        elif ls == 0:
            raise error.CantFind(word)
        else:
            raise error.Ambiguity(word, stuff)

    def findDirection(self, destination):
        """Thing.findDirection(destination) -> string

        Search this room's list of exits for a given destination, and
        return the direction it is in, returning None if no such
        reverse exists.  (Note: this is slow.)
        """
        for k, v in self.__exits.items():
            if v == destination:
                return k
        return None

    def findExit(self, direction):
        """Thing.findExit(direction) -> Thing
        Search this Room's list of exits for the given name.  raise
        NoExit if not found.
        """

        try:
            where=self.__exits[direction]
        except KeyError:
            raise error.NoExit(self,direction)
        else:
            if reflect.isinst(where,Thing):
                if where.destination:
                    return where.destination
                if not where.enterable:
                    raise error.NoExit(self,direction)
                return where
            elif reflect.isinst(where,types.StringType):
                raise error.NoExit(self,direction,where)

    def set_description(self,description):
        """Thing.description = string OR hash
        Set the basic (__MAIN__) description element to be the given
        description OR add a dictionary's key:values to the description.

        This is a convenience function.  See 'describe'."""
        if (type(description)==types.StringType or
            callable(description)):
            self.describe("__MAIN__", description)
        elif (type(description)==types.DictType or
              reflect.isinst(description,observable.Hash)):
            for foo, bar in description.items():
                self.describe(foo, bar)
        else:
            assert 0, "Not a valid description"

    def get_description(self):
        if type(self.__description['__MAIN__']==types.StringType):
            return self.__description['__MAIN__']
        return "<not a string>"


    def describe(self, key, value):
        """Thing.describe(key, value) -> None
        Set a description element of this Thing."""
        # this is slightly hacky, but it prevents re-broadcast of
        # redundant data.
        hk = self.__description.has_key(key)
        if not (hk and type(value) is types.StringType
                and self.__description[key] == value):
            self.publish('description',(key,value))
            if value is None:
                if hk:
                    del self.__description[key]
            else:
                self.__description[key] = value

    def set_exits(self, exits):
        """Thing.exits = {direction:room,...}
        Add a dictionary of name:exit pairs to this Room's exits list.
        """
        # keep in mind that setting the exits is additive.
        for direction, room in exits.items():
            self.connectExit(direction, room)

    def connectExit(self, direction, room):
        """Thing.connectExit(direction, room)

        add an exit to this room, exiting in the specified direction
        to the specified other room. """
        self.publish('exit', Event(direction=direction,
                                   destination=room))
        self.__exits[direction] = room

    def disconnectExit(self, direction):
        """Thing.disconnectExit(direction)

        Remove an exit from this room, exiting in the specified
        direction to the specified other room. """
        del self.__exits[direction]
        self.publish('exit', Event(direction=direction,
                                   destination=None))

    ### Persistence

    def __upgrade_0(self):
        print 'upgrading from version 0 to version 1'

    def __upgrade_1(self):
        print 'upgrading',self,'from version 1 to version 2'
        self._containers = [self.location]
        self._contained = []
        for child in self.__contents.keys():
            if child.location is self:
                self._contained.append(child)

    def __upgrade_2(self):
        print 'upgrading',self,'from version 2 to version 3'
        if self._containers == [None]:
            self._containers = []

    def __v3UpgradeRemoveSyns(self, sub):
        if self not in sub._containers:
            self._contained.remove(sub)
            for synonym in sub.synonyms:
                self.__remref(synonym, sub)
    
    def __upgrade_3(self):
        print 'upgrading',self,'from version 3 to version 4:',
        del self.__contents
        if self.__dict__.has_key('place'):
            del self.__dict__['place']
        # in this version, contents and
        if hasattr(self, '_dov3update'):
            for loc in self._dov3update:
                print '-',
                loc.__v3UpgradeRemoveSyns(self)
            del self._dov3update
                
        for contained in copy.copy(self._contained):
            # haven't initialized the other object yet
            print '.',
            if hasattr(contained, '_containers'):
                print '.',
                self.__v3UpgradeRemoveSyns(contained)
            else:
                print 'x',
                v3uplst = getattr(contained, '_dov3update', [])
                v3uplst.append(self)
                contained._dov3update = v3uplst
        print '!'

    def __setstate__(self, dict):
        """Persistent state callback.
        """
        assert self.__version <= Thing.__version
        self.__dict__.update(dict)
        while self.__version != Thing.__version:
            getattr(self,'_Thing__upgrade_%s' % self.__version)()
            self.__version = self.__version + 1

    def __getstate__(self):
        """Persistent state callback.
        """
        dict = copy.copy(self.__dict__)

        for k, v in dict.items():
            if (reflect.isinst(v, styles.Ephemeral) or
                # FIXME: sometimes (web distribution) it's OK to pickle
                # protocols.  Here, it's not.  Jury's still out on this one.
                reflect.isinst(v, protocol.Protocol)):
                del dict[k]

        if dict.has_key('code_space'):
            cs = copy.copy(dict['code_space'])
            if cs.has_key('__builtins__'):
                del cs['__builtins__']
                dict['code_space'] = cs
        return dict

    def printSource(self,write):
        """Print out a Python source-code representation of this object.
        
        See the source code for a detailed description of how this is done; it
        is not expected to be 100% reliable, merely informative.
        """
        if (not hasattr(self.reality,'sourcemods') or not
            self.reality.sourcemods.has_key(self.__class__.__module__)):
            write("import %s\n"%self.__class__.__module__)
            if hasattr(self.reality,'sourcemods'):
                self.reality.sourcemods[self.__class__.__module__]=1

        write("%s.%s(%s)(\n"%(self.__class__.__module__,
                              self.__class__.__name__,
                              repr(self.name)))

        # now, about that 'hack'...
        dct = copy.copy(self.__dict__)

        # These will all automatically be re-generated when the object
        # is constructed, so they're not worth writing to the file.
        ephemeral = ('_Thing__index',
                     '_Thing__version',
                     '_contained',
                     'reality',
                     'thing_id',
                     'changed',
                     'place',
                     # Not exactly ephemeral, but specified in the
                     # constructor.
                     'name')

        for eph in ephemeral:
            if dct.has_key(eph):
                del dct[eph]

        s = copy.copy(dct['_Thing__synonyms'])
        del dct['_Thing__synonyms']
        # take my name out of the synonyms list
        s.remove(string.lower(self.name))
        
        # if I've got a displayName, and it's a string, remove it from my list
        # of synonyms too.
        
        if type(self.displayName) is types.StringType:
            s.remove(string.lower(self.displayName))
            
        if s:
            dct['synonyms']=s

        c = copy.copy(dct['_containers'])
        del dct['_containers']

        # I can't keep my location in the sourced map, because it will
        # happily call grab twice; so in the map, the 'containers'
        # attribute represents *additional* containers (which is what
        # setting it would do anyway)
        try:
            c.remove(self.location)
        except:
            pass
        if c:
            dct['containers'] = c


        if dct.has_key("subscribers"):
            subs = copy.copy(dct['subscribers'])

            # If I only have WhenMethod subscribers (or no subscribers at
            # all) this attribute is superfluous.

            # Other subscribers will also probably not write out to source
            # properly, but WhenMethodSubscriptions will be set up
            # automatically again (assuming all the attributes stay
            # correct!) so I won't make the map unparseable unless it's
            # necessary to indicate something I won't replicate properly
            # next time.

            for k,sub in subs.items():
                try:
                    for subn in sub:
                        if not reflect.isinst(subn,
                                              observable.
                                              WhenMethodSubscription):
                            raise 'stop'
                    del subs[k]
                except 'stop':
                    pass

            if subs:
                dct['subscribers'] = subs
            else:
                del dct['subscribers']

        exits = dct['_Thing__exits']
        del dct['_Thing__exits']
        if exits:
            dct['exits'] = exits
        if dct.has_key('focus') and dct.has_key('location'):
            if dct['focus']==dct['location']:
                del dct['focus']

        if dct.has_key('code_space'):
            del dct['code_space']

        if dct.has_key('intelligence'):
            # i=dct['intelligence']
            # if reflect.isinst(i,LocalIntelligence):
            del dct['intelligence']

        d = dct['_Thing__description']
        del dct['_Thing__description']

        if len(d) == 1 and d.has_key('__MAIN__'):
            d = d['__MAIN__']

        dct['description'] = d

        # Since this class is synchronized, it may have allocated a
        # lock.  It's certainly not necessary to keep track of that.

        if dct.has_key('_threadable_lock'):
            del dct['_threadable_lock']

        # whew.  let's just pretend like THAT didn't happen.

        # oh by the way, this is more for human readability than
        # anything.  since you can end up with [...] lists and what
        # have you.

        # Remove all ephemeral objects (network connections, et. al.)
        for k, v in dct.items():
            if reflect.isinst(v, styles.Ephemeral):
                del dct[k]

        items = dct.items()
        # sort according to attribute name
        items.sort(lambda a, b: cmp(a[0], b[0]))
        for k, v in items:
            v = source.sanitize(v)
            # delete keys from the dictionary as we go, in order to
            # format the end of the argument list properly (with no comma)
            del dct[k]
            if dct:
                nn = ','
            else:
                nn = ''
            write("\t%s=%s%s\n" % (k,repr(v),nn))

        write(")\n")

# End of Thing

threadable.synchronize(Thing)
observable.registerWhenMethods(Thing)
