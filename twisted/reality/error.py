
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

import random
import string

import cStringIO
StringIO = cStringIO
del cStringIO

class RealityException(Exception):
    """RealityException()

    This is the base superclass of all formattable exceptions."""


class InappropriateVerb(Exception):
    """InappropriateVerb()

    This exception is not formattable: raise it if you want to cease
    executing and default to another verb down the parse chain."""

class CantFind(RealityException):
    """
    This exception is raised when an object cannot be found.
    """
    def __init__(self,name):
        RealityException.__init__(self,name)
        self.name=name
    def format(self, observer=None):
        return "I can't see a %s here." % self.name

class Ambiguity(RealityException):
    """Ambiguity(word, list of things)
    An exception that gets raised when it's not clear what a player is
    referring to.
    """
    def __init__(self, word, list):
        RealityException.__init__(self, word, list)
        self.word=word
        self.list=list

    def format(self,observer=None):
        x=StringIO.StringIO()
        x.write("When you say %s, do you mean " % self.word)
        lx=len(self.list)
        i=0
        while i < lx:
            z=self.list[i].nounPhrase(observer=observer)
            if i == lx-1:
                x.write("or %s?"%z)
            else:
                x.write("%s, "%z)
            i=i+1
        return x.getvalue()

class Failure(RealityException):
    """
    This exception is a general indication of failure of some
    twisted.reality-oriented operation.
    """
    def __init__(self,*args,**kw):
        apply(RealityException.__init__,((self,)+args),kw)
        raise self
    def format(self,observer=None):
        if observer:
            return observer.format(self.args)
        else:
            return string.join(self.args)

class NoVerb(RealityException):
    """
    This exception is raised when no appropriate action could be located for
    the specified verb.
    """
    errors=["You don't think that you want to waste your time with that.",
            "There are probably better things to do with your life.",
            "You are nothing if not creative, but that creativity could be better applied to developing a more productive solution.",
            "Perhaps that's not such a good idea after all.",
            "Surely, in this world of limitless possibility, you could think of something better to do.",
            "An interesting idea...",
            "A valiant attempt.",
            "What a concept!",
            "You can't be serious."]
    def __init__(self,verb):
        RealityException.__init__(self, verb)
        self.verb=verb
    def format(self,observer=None):
        errors=self.errors
        try: errors = observer.noverb_messages
        except: pass
        return errors[random.randint(0,len(errors)-1)]

class NoObject(RealityException):
    """
    This exception is raised when a requested direct/indirect object does not
    represent a locatable Thing.
    """
    def __init__(self,mstr):
        RealityException.__init__(self, mstr)
        self.string=mstr

    def format(self,observer=None):
        return "There is no %s here."%self.string

class TooManyObjects(Failure):
    """
    This exception is raised when a sentence is cluttered with unnecessary
    objects.
    """


class NoExit(RealityException):
    """
    This exception is raised when a certain exit is not available.
    """
    def __init__(self,room,string,error=None):
        RealityException.__init__(self, room, string, error)
        self.room=room
        self.string=string
        self.error=error

    def format(self,observer=None):
        if self.error:
	    return self.error
        else:
	    return "You can't go %s from here."%self.string

class NoString(RealityException):
    """
    This exception is raised when a sentence does not contain a requested
    direct/indirect string.
    """
    def __init__(self,verb,prep):
        RealityException.__init__(self, verb, prep)
        self.verb=verb
        self.prep=prep

    def format(self, observer=None):
        xio=StringIO.StringIO()
        xio.write("What do you want to ")
        xio.write(self.verb)
        if (self.prep):
            xio.write(" ")
            xio.write(self.prep)
        xio.write("?")
        return xio.getvalue()
