
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


"""Twisted Reality ][

This is the simulation core of a single OR multi player text-based game.
"""

# System Imports
from copy import copy
import string

# Twisted Imports
import twisted
from twisted.python import reflect, reference, delay
from twisted.spread import pb
from twisted.cred import identity
from twisted.persisted import styles

# Sibling Imports
import player

class Reality(delay.Delayed,
              reference.Resolver,
              pb.Service,
              styles.Versioned):

    serviceName = 'twisted.reality'
    def __init__(self, name='twisted.reality', app=None):
        delay.Delayed.__init__(self)
        reference.Resolver.__init__(self, self)
        pb.Service.__init__(self, name, app)
        self.__counter = 0
        self.__ids = {}
        self.__names = {}

    def addPlayersAsIdentities(self):
        """Add all players with passwords as identities.
        """
        for th in self.__ids.values():
            if isinstance(th, player.Player) and hasattr(th, 'password'):
                styles.requireUpgrade(th)
                idname = th.name
                print "Adding identity %s" % idname
                ident = identity.Identity(idname, self.application)
                ident.setAlreadyHashedPassword(th.password)
                ident.addKeyForPerspective(th)
                try:
                    self.application.authorizer.addIdentity(ident)
                except KeyError:
                    print 'unable to add reality identity for %s' % idname

    def __setstate__(self, state):
        # mix the two varieties of state together.
        styles.Versioned.__setstate__(self, state)
        delay.Delayed.__setstate__(self, self.__dict__)

    persistenceVersion = 1

    def upgradeToVersion1(self):
        print 'Upgrading Twisted Reality instance.'
        from twisted.internet.app import theApplication
        styles.requireUpgrade(theApplication)
        pb.Service.__init__(self, 'twisted.reality', theApplication)
        self.addPlayersAsIdentities()

    def getThingById(self, thingid):
        return self.__ids[thingid]

    ### PB
    def getPerspectiveNamed(self, playerName):
        """Get a perspective from a named player.

        This will dispatch to an appropriate player by locating the named
        player.
        """
        return self[playerName]

    def _addThing(self,thing):
        """(internal) add a thing to this reality
        """
        self.__counter = self.__counter+1
        thing.thing_id = self.__counter
        idname = string.lower(thing.name)
        assert not self.__ids.has_key(thing.thing_id),\
               "Internal consistency check failure."\
               "I don't know what's going on."
        assert not self.__names.has_key(idname),\
               "Invalid name '%s'.  You must choose one that's "\
               "not yet in use in this Reality." % idname
        self.__ids[thing.thing_id] = thing
        self.__names[idname] = thing
        self.changed = 1


    def _removeThing(self,thing):
        """(internal) remove a thing from this reality
        """
        if self.__ids.get(thing.thing_id) is thing:
            del self.__ids[thing.thing_id]
        else:
            print "WARNING:",thing," ID CANNOT BE REMOVED FROM",self
        lname = string.lower(thing.name)
        if self.__names.get(lname) is thing:
            del self.__names[lname]
        else:
            print "WARNING:",thing," NAME CANNOT BE REMOVED FROM",self
        self.changed = 1


    def unplaced(self):
        """return a list of objects in this Reality that have no place
        """
        return filter(lambda x: not x.location, self.__ids.values())


    def _updateName(self,thing,oldname,newname):
        assert (not oldname) or self.__names[string.lower(oldname)] is thing , 'Bad mojo.'
        if oldname:
            del self.__names[string.lower(oldname)]
        self.__names[string.lower(newname)]=thing


    def __getitem__(self,name):
        return self.__names[string.lower(name)]

    def get(self, name,defarg = None):
        return self.__names.get(string.lower(name),defarg)


    def objects(self):
        return self.__ids.values()

    def resolveAll(self):
        self.resolve(self.objects())

    def printSource(self,write):
        "Create a source representation of the map"
        self.sourcemods={}

        write("""
#
# This file was auto-generated by Twisted Reality.
#

from twisted.python import reference
from twisted.reality import thing
from twisted.reality import reality
t=reference.Reference
m=reference.AttributeReference
result = thing._default = reality.Reality('%s')

""" % self.getServiceName())
        oo = self.objects()
        oo.sort(lambda x, y: cmp(string.lower(x.name),
                                 string.lower(y.name)))

        for o in oo:
            o.printSource(write)
            write("\n\n")

        write("del thing._default\n")
        del self.sourcemods


def fromSourceFile(pathName, application=None):
    """Load a Reality from a Python source file.

    I will load and return a Reality from a python source file, similiar to one
    output by Reality.printSource.  I will optionally attach it to an
    application.
    """
    
    ns = {}
    execfile(pathName, ns, ns)
    result = ns['result']
    result.resolveAll()
    if application:
        result.setApplication(application)
        application.addDelayed(result)
    result.addPlayersAsIdentities()
    return result
