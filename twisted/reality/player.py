
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


# System Imports
import string
import cPickle
import os
import traceback
import time


# Twisted Imports
from twisted.python import threadable, reflect, log, authenticator, rebuild
from twisted.spread import pb
from twisted.persisted import styles

# Sibling Imports
import thing
import error
import room
import sentence
import geometry

#import cStringIO as StringIO..
import cStringIO
StringIO = cStringIO
del cStringIO

class Player(styles.Versioned, thing.Thing, pb.Perspective):
    """Player

    A convenience class for sentient beings (implying turing-test quality AI)
    """
    def __init__(self, name, reality='', identityName="Nobody"):
        """Initialize me.
        """
        self.identityName = identityName
        thing.Thing.__init__(self, name, reality)

    def __getstate__(self):
        st1 = thing.Thing.__getstate__(self)
        st2 = styles.Versioned.__getstate__(self, st1)
        return st2

    persistentVersion = 1

    def upgradeToVersion1(self):
        print 'upgrading player',self.name
        pb.Perspective.__init__(self, self.name, self.reality)

    def set_reality(self, reality):
        if self.reality is reality:
            return
        assert self.reality is None, 'player migration not implemented.'
        thing.Thing.set_reality(self, reality)
        pb.Perspective.__init__(self, self.name, self.reality, self.identityName)

    def set_service(self, svc):
        """Don't really set the service, since it can be retrieved through self.reality.
        """
        assert svc == self.reality, "Service _must_ be the same as reality."
    
    def get_service(self):
        """Return my reality, so that it's not duplicately stored.

        This is so that my passport.Perspective methods work properly.
        """
        return self.reality
    
    hollow = 1
    def indefiniteArticle(self, observer):
        return ""

    def containedPhrase(self, observer, held):
        return "%s is holding %s." % (string.capitalize(self.nounPhrase(observer)),
                                      held.nounPhrase(observer))

    definiteArticle=indefiniteArticle
    aan=indefiniteArticle
    the=definiteArticle

    ### Remote Interface

    def perspective_execute(self, st):
        self.execute(st)

    def attached(self, remoteIntelligence, identity):
        """A user-interface has been attached to this player.

        This equates to a message saying that they're logged in.  It takes one
        argument, the interface.  This will be signature-compatible with
        RemoteIntelligence.  This is an implementation of::

            twisted.internet.passport.Perspective.attached(reference, identity)

        and therefore follows those rules.
        """
        if hasattr(self, 'intelligence'):
            log.msg("player duplicate: [%s]" % self.name)
            raise authenticator.Unauthorized("Already logged in from another location.")
        log.msg("player login: [%s]" % self.name)
        if hasattr(self, 'oldlocation'):
            self.location = self.oldlocation
            del self.oldlocation
        self.intelligence = LocalIntelligence(remoteIntelligence)
        return self

    def detached(self, remoteIntelligence, identity):
        log.msg("player logout: [%s]" % self.name)
        del self.intelligence
        self.oldlocation = self.location
        self.location = None

    ### Basic Abilities

    def ability_go(self, sentence):
        """Move in a direction.
        """
        direct = sentence.directString()
        where = self.location.findExit(direct)

        # TODO: calculations as to whether I will *fit* in
        # this wonderful new place I've discovered

        self.hears("You go ", direct,".")
        self.location = where

    def ability_look(self, sentence):
        """Change focus to an object or refresh current focus.
        """
        try:
            object = sentence.indirectObject('at')
        except error.NoString:
            object = self.place
        self.focus = object

    def ability_take(self, sentence):
        """Place an object in this Player.
        """
        object = sentence.directObject()
        if object.location is self:
            error.Failure("You were already holding that.")
        else:
            object.move(destination = self, actor = self)
            self.hears(object,": Taken.")

    ability_get = ability_take  # this is where it all started

    def ability_wait(self, sentence):
        """Waste one move.
        """
        self.hears("Time passes...")

    def ability_drop(self, sentence):
        """Place an object currently in this player into the Room which contains them.
        """
        object = sentence.directObject()
        if object.location == self:
            object.move(destination = self.place, actor = self)
            self.hears(object,": Dropped.")
        else:
            self.hears("You weren't holding that.")

    def ability_inventory(self,sentence):
        """Pretty-print the list of things this Player is holding.
        """
        strings = map(lambda f, self=self: f.nounPhrase(self),
                      self.getThings(self))
        if len(strings) == 0:
            self.hears("You aren't carrying anything.")
        else:
            if len(strings) > 1:
                strings[-1] = 'and '+strings[-1]
            if len(strings) == 2:
                fin = string.join(strings)
            else:
                fin = string.join(strings,', ')
            self.hears("You are carrying "+fin+'.')

    def ability_say(self, sentence):
        """Say a text string.
        """
        self.broadcastToOne(to_subject = ('You say, "%s".' %
                                          sentence.directString()),
                            to_other   = (self,' says, "%s"' %
                                          sentence.directString()))
        
    def ability_emote(self, sentence):
        """`emote' a text string (perform an arbitrary action with no effect on the world).
        """
        self.location.allHear('* ',self,' ',sentence.directString())

    def ability_ls(self, sentence):
        """reminds the user to switch back to a shell.
        """
        self.hears(r"""__      ___ __ ___  _ __   __ _ 
\ \ /\ / / '__/ _ \| '_ \ / _` |
 \ V  V /| | | (_) | | | | (_| |
  \_/\_/ |_|  \___/|_| |_|\__, |
                          |___/ 
          _           _               
__      _(_)_ __   __| | _____      __
\ \ /\ / / | '_ \ / _` |/ _ \ \ /\ / /
 \ V  V /| | | | | (_| | (_) \ V  V / 
  \_/\_/ |_|_| |_|\__,_|\___/ \_/\_/""")



class Intelligence:
    """
    An 'abstract' class, specifying all methods which TR user
    interfaces must implement.
    """

    def seeName(self, name):                         pass
    def seeItem(self, thing,name):                   pass
    def dontSeeItem(self, thing):                    pass
    def seeNoItems(self):                            pass
    def seeExit(self, direction, exit):              pass
    def dontSeeExit(self, direction):                pass
    def seeNoExits(self):                            pass
    def seeDescription(self, key, description):      pass
    def dontSeeDescription(self, key):               pass
    def seeNoDescriptions(self):                     pass
    def seeEvent(self, string):                      pass
    def request(self, question,default,c):   cancel()

class RemoteIntelligence:
    """
    An interface to preserve bandwidth, and keep the number of remote
    references minimal.  This wasn't strictly necessary, but it seems
    cleaner to have it.
    """
    def seeName(self, name):                        pass
    def seeItem(self, thing, parent, value):    pass
    def dontSeeItem(self, thing, parent):        pass
    def seeNoItems(self):                       pass
    def seeExit(self, direction):               pass
    def dontSeeExit(self, direction):            pass
    def seeNoExits(self):                       pass
    def seeDescription(self, key, desc):         pass
    def dontSeeDescription(self, key):             pass
    def seeNoDescriptions(self):                  pass
    def seeEvent(self, string):                       pass
    # ain't nothin' you can do about this.
    def request(self, question,default,c): pass

class LocalIntelligence(Intelligence):
    """
    This translates local intelligence calls to remote intelligence
    calls.
    """
    remote=None
    def __init__(self,remote):
        self.remote=remote
    def seeName(self, name):
        self.remote.seeName(name)
    def seeItem(self, thing,name):
        self.remote.seeItem(id(thing),
                             id(thing.place),
                             name)
    def dontSeeItem(self, thing):
        self.remote.dontSeeItem(id(thing),
                                id(thing.place))
    def seeNoItems(self):
        self.remote.seeNoItems()
    def seeExit(self, direction, exit):
        self.remote.seeExit(direction)
    def dontSeeExit(self, direction):
        self.remote.dontSeeExit(direction)
    def seeNoExits(self):
        self.remote.seeNoExits()
    def seeDescription(self, key, description):
        self.remote.seeDescription(key,description)
    def dontSeeDescription(self, key):
        self.remote.dontSeeDescription(key)
    def seeNoDescriptions(self):
        self.remote.seeNoDescriptions()
    def seeEvent(self, string):
        self.remote.seeEvent(string)
    def request(self, question,default,c):
        self.remote.request(question,default,c)


def discover(name,x,y,z,
             north=1,east=1,west=1,south=1,up=1,down=1):
    """
    Jedin's `discover' verb from Divunal Classic.
    """
    # this is arbitrary, so:
    #    pos   neg
    # z= north-south
    # y= up-down
    # x= east-west
    matrix=[]
    for i in range(x):
        xrow=[]
        for j in range(y):
            zrow=[]
            for k in range(z):
                zrow.append(room.Room('%s (%d,%d,%d)'%(name,i,j,k)))
            xrow.append(zrow)
        matrix.append(xrow)
    for i in range(x):
        for j in range(y):
            for k in range(z):
                if south:
                    if k > 0:
                        matrix[i][j][k].connectExit('south',matrix[i][j][k-1])
                if north:
                    if k < z-1:
                        matrix[i][j][k].connectExit('north',matrix[i][j][k+1])
                if west:
                    if i > 0:
                        matrix[i][j][k].connectExit('west',matrix[i-1][j][k])
                if east:
                    if i < x-1:
                        matrix[i][j][k].connectExit('east',matrix[i+1][j][k])
                if down:
                    if j > 0:
                        matrix[i][j][k].connectExit('down',matrix[i][j-1][k])
                if up:
                    if j < y-1:
                        matrix[i][j][k].connectExit('up',matrix[i][j+1][k])


    return matrix


def persist_log(author, reality, filename, time):
    log.msg("%s persisted %s to %s.rp at %s" % (author, reality.name, filename, asctime(gmtime(time))))


class Author(Player):

    wizbit = 1

    def __init__(self,*args,**kw):
        apply(Player.__init__,(self,)+args,kw)
        self.code_space={'self':self,
                         'Thing':thing.Thing,
                         'log_dig':None,
                         'log_create':None,
                         'log_persist':persist_log,
                         'trashcan':None,
                         #'__builtins__':None
                         }


    def ability_adduser(self, sentence):
        """adduser (name)
Adds a new user to the map.
"""
        name = sentence.directString()
        p = Player(name)
        p.location = self.place
        self.hears('poof')

    def ability_nail(self, sentence):
        """nail object
this sets the component bit of an object."""
        sentence.directObject().component = 1

    def execute(self, string):
        """
        overrides execute from Player; this adds the "$python" capability.
        """
        if string != "" and string[0]=='$':
            try:
                return self.runcode(string[1:])
            except error.RealityException, re:
                self.hears(re.format(self))
                return re
        else:
            return Player.execute(self,string)

    def runcode(self, cmd):
        """
        Run a block of code as this user.
        """
        fn='$'+self.name+'$'
        try:    code=compile(cmd,fn,'eval')
        except:
            try: code=compile(cmd,fn,'single')
            except:
                error.Failure("That won't compile.")

        try:
            val=eval(code,self.code_space)
            if val is not None:
                self.hears(repr(val))
                return val
        except:
            sio=StringIO.StringIO()
            traceback.print_exc(file=sio)
            error.Failure(sio.getvalue())

    def ability_snippet(self, sentence):
        """snippet {name}
This creates an arbitrarily named string in your namespace from a
response-request and runs it as a block of python code.  BE CAREFUL when using
this; do not define functions, for example, or they will render your map
unpickleable.
        """
        snipname = sentence.directString()
        def cancel(self): pass
        def ok(self,code,o=self, snipname=snipname):
            cs = o.code_space
            cs[snipname] = code
            try:
                code = compile(code, '$$'+o.name+'$$', 'exec')
                exec code in cs, cs
            except:
                sio = StringIO.StringIO()
                traceback.print_exc(file=sio)
                o.hears(sio.getvalue())
                
        c = Referenced()
        c.remote_ok = ok
        c.remote_cancel = cancel
        
        code = self.code_space.get(snipname, "")
        self.request("Snippet %s" % snipname,code,c)


    def ability_describe(self,sentence):
        """describe object
this will prompt you for a description.  enter something."""

        obj = sentence.directObject()

        def setdesc(desc, obj=obj):
            obj.description = desc
        def forgetit():
            pass
        c = pb.Referenced()
        c.obj = obj
        c.remote_ok=setdesc
        c.remote_cancel=forgetit

        desc=obj.get_description()
        if desc != "<not a string>":
            self.request("Please describe %s"%obj.nounPhrase(self),desc,c)
        else:
            self.hears(
                "That object's description is a dynamic property -- "
                "you probably shouldn't mess "
                "with it directly.  Take a look at the source for details.")

    def ability_mutate(self, sentence):
        """mutate object to new_type

This will mutate an object into a different type of object. """
        mutator=sentence.directObject()
        try:
            newtype=sentence.indirectString('to')
            newtype=self.code_space[newtype]
        except:
            error.Failure("You don't know of any such type.")
        newtype=reflect.getcurrent(newtype)
        x=issubclass(newtype,reflect.getcurrent(thing.Thing))
        assert x, "You shouldn't mutate Things to types which are not Things."
        if not reflect.isinst(mutator,newtype):
            mutator.__class__=newtype

    def ability_scrutinize(self,sentence):
        """scrutinize object

display some code which may be helpful..."""

        object=sentence.directObject()

        stio=StringIO.StringIO()
        object.printSource(stio.write)

        # This should print to 'hears' until requestResponse works in
        # the telnet client (I have no idea how that should work yet,
        # really... tf's editing support for other MOOs should be an
        # inspiration)

        self.hears(stio.getvalue())

    def ability_import(self, sentence):
        """import (object|.python.object) [to varname]

If you have a pathname that starts with a '.', this will attempt to load a
module and import the last thing on the dotted path.  (For example, if you say
'import .twisted.reality.thing.Thing', that would be equivalent to 'from
twisted.reality.thing import Thing'.  Otherwise, it attempts to search for an object
and import it as the synonym you specify. (Spaces will be replaced with
underscores.) """

        ds=sentence.directString()
        if ds[0]=='.':
            ds=ds[1:]
            if ds:
                dt=string.split(ds,'.')
                dt=map(string.strip,dt)
                if len(dt)==1:
                    st='import %s'%dt[0]
                else:
                    st='from %s import %s'%(string.join(dt[:-1],'.'),dt[-1])
                self.runcode(st)
                self.hears("%s: success."%st)
        else:
            dt = sentence.directObject()
            ds = string.replace(ds,' ','_')
            self.code_space[ds]=dt
            self.hears("You remember %s as %s."%(dt.nounPhrase(self),repr(ds)))

    def ability_rebuild(self, sentence):
        """rebuild (name|.python.name)

This will rebuild either a Thing (reloading its toplevel module (the one that
its class is in) and changing its class as appropriate.), an object in your
namespace, or a qualified python module name (prefixed with a dot).  """

        ds=sentence.directString()

        if ds[0]=='.':
            module=string.replace(ds[1:],' ','')
            rebuild.rebuild(reflect.named_module(module))
        else:
            try:    object=self.code_space[ds]
            except:    object=sentence.directObject()

            if reflect.isinst(object,thing.Thing):
                rebuild.rebuild(reflect.named_module(object.__class__.__module__))
            else:
                rebuild.rebuild(object)

    def ability_help(self, sentence):
        """help {commandname}
For help with a command, type help followed by the command you would like help
with. For example, for help with the dig command, type "help dig"."""
        try:
            toHelpWith = sentence.directString()
        except error.NoString:
            error.Failure(self.ability_help.__doc__)
        try:
            vb = self.getAbility(toHelpWith)
            self.hears(vb.__doc__)
            return
        except AttributeError:
            pass
        self.hears("I'm not familiar with that ability.")

    def ability_commands(self, sentence):
        """Usage: commands
Commands will print a list of all the various commands and inherent abilities
your character has."""
        dict = {}
        reflect.addMethodNamesToDict(self.__class__, dict, 'ability_')
        self.hears("You have the following abilities:")
        for x in dict.keys():
            self.hears(x)

    def ability_persist(self, sentence):
        """persist {mapname}

        This will create a file called mapname.rp, containing the
        saved state of the current game."""
        if self.code_space.has_key('log_persist') and self.code_space['log_persist'] is not None:
            self.code_space['log_persist'](self.name, self.reality, sentence.directString(),time.time())
        file=open(sentence.directString()+'.rp','wb')
        cPickle.dump(self.reality,file)
        file.flush()
        file.close()

        self.hears('Saved "%s.rp".'%sentence.directString())


    def ability_cvs(self, sentence):
        """cvs update

        Currently, this just updates the entire cvs repository.
        """
        proc = os.popen('cvs update 2>&1')
        self.hears("CVS updating...")
        for line in proc.readlines():
            self.hears(string.strip(line))
        self.hears("Done.")

    def ability_source(self, sentence):
        """source {thing}
This creates a file called thing.py, containing the source for the thing in question."""
        file=open(sentence.directString()+"_rp.py",'wb')
        def writeln(bytes,file=file):
            file.write(bytes)
        self.reality.printSource(writeln)

    def ability_portal(self, sentence):
        """portal {direction} to {room}

Portal creates a new, one-way passage from the room you are currently in to the
room specified by "to". (For example, "portal east to mansion basement" would
create a new exit to the east, leading to the "mansion basement" room. Note
that this would NOT create a corresponding exit in "mansion basement" leading
back to the room you were in.) This can be undone with "barricade". See also
"tunnel" and "dig"."""

        direction=sentence.directString()
        try:
            rs = sentence.indirectString('to')
            r = self.reality.get(rs)
            p = self.place
            p.connectExit(direction, r)
        except:
            self.hears("Please specify a destination room! (For example, \"dig west to mansion cellar\")")

    def ability_barricade(self, sentence):
        """barricade {direction}
Barricade will close the exit leading in the given direction, if it exists. Note that this will only close the direction you have specified, and not the way back (if there is one.) Compare \"untunnel\", see also \"undig\"."""
        direction = sentence.directString()
        self.place.disconnectExit(direction)

    def ability_undig(self, sentence):
        """undig {direction}
Undig is the opposite of dig, in that it will close off the exit in the given direction, as well as destroying the room it leads to, so use it carefully. See also Dig, compare \"untunnel\", \"barricade\"."""
        direction = sentence.directString()
        otherPlace = self.place.findExit(direction)
        self.place.disconnectExit(direction)
        if self.code_space.has_key('trashcan') and self.code_space['trashcan']  is not None:
            otherPlace.location = self.code_space['trashcan']
        else:
            otherPlace.destroy()

    def ability_tunnel(self, sentence):
        """untunnel {direction} to {room}

Tunnel creates a new, two-way passage in the room you are currently in, which
links to the room specified with "to" and back again. (For example, "tunnel
west to mansion cellar" would create a new exit to the west, leading to the
"mansion cellar" room, and also add an east exit to "mansion cellar" that led
back to the room you're currently in.) This can be easily undone with
"untunnel". Compare "dig" and ""."""

        direction=sentence.directString()
        try:
            rs = sentence.indirectString('to')
            r = self.reality.get(rs)
            p = self.place
            p.connectExit(direction, r)
            r.connectExit(geometry.reverse(direction),p)
        except:
            self.hears("Please specify a destination room! (For example, \"dig west to mansion cellar\")")

    def ability_untunnel(self, sentence):
        """untunnel {direction}

Untunnel removes both directions of the exit in the given direction. (e.g. If
you "untunnel west", it will block the exit leading west, as well as the exit
leading east from the room that the west exit used to connect to.) See also
"tunnel", compare "barricade", "undig"."""

        direction = sentence.directString()
        otherPlace = self.place.findExit(direction)
        self.place.disconnectExit(direction)
        otherPlace.disconnectExit(geometry.reverse(direction))

    def ability_dig(self, sentence):
        """dig {direction}

Dig creates a new room (and an exit to that room from the current room, and
back again) in the direction specified. See also "undig" to totally undo this
process, or "tunnel" and "barricade" to edit or create new exits for your
new room."""
        direction=sentence.directString()
        try:
            name = sentence.indirectString('to')
        except:
            name = "Untitled Room"
        p = self.place
        r = room.Room(name,self.reality)
        p.connectExit(direction, r)
        r.connectExit(geometry.reverse(direction),p)
        if self.code_space.has_key('log_dig') and self.code_space['log_dig'] is not None:
            self.code_space['log_dig'](self.name, r,time.time())


    def ability_create(self,sentence):
        """create {name}

Creates a new Thing with the name you provide. See also "destroy"."""
        if self.code_space.has_key('log_create') and self.code_space['log_create'] is not None:
            self.code_space['log_create'](self.name,obj,time.time())
        obj = thing.Thing(sentence.directString())
        obj.location = self
        self.hears("*poof* ",obj.nounPhrase," was created.")

    def ability_destroy(self, sentence):
        """destroy {name}

Destroys the named Thing, unless Author has 'trashcan' set, in which
case the object is relocated to the specified trashcan. See also
"create"."""
        obj = sentence.directObject()
        if self.code_space.has_key('trashcan') and self.code_space['trashcan']  is not None:
            obj.location = self.code_space['trashcan']
            self.hears("*kchunk* ",obj.nounPhrase," was trashcanned.")
        else:
            obj.destroy()
            self.hears("*foop* ",obj.nounPhrase," was destroyed.")

    def ability_locate(self, sentence):
        """locate {Thing}

Tells you the current location of the named Thing, assuming it exists. Note
that you must provide the "true" name of the Thing being located, and not just
one of it's synonyms."""
        dstring = sentence.directString()
        obj = self.reality.get(dstring)
        if (obj):
            if (not obj.location):
                self.hears(obj.capNounPhrase, " exists, but is nowhere in particular.")
            else:
                self.hears(obj.capNounPhrase, " is currently in \"",obj.location,"\"")
        else:
            self.hears("There doesn't seem to be "+sentence.aan(dstring)+"\""+dstring+"\" in this reality...")

threadable.synchronize(Author)
