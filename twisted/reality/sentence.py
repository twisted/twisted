
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
import UserList
import tokenize
import copy
import string
import cStringIO
StringIO = cStringIO
del cStringIO

# Twisted Imports
from twisted.python import reflect


# Sibling Imports
import thing
import error

def aan(name):
    """Utility which returns 'a' or 'an' for a given noun.
    """
    if string.lower(name[0]) in ('a','e','i','o','u'):
        return 'an '
    else:
        return 'a '

def AAn(name):
    """Utility which returns 'A' or 'An' for a given noun.
    """
    return string.capitalize(aan(name))

class PseudoSentence:
    """
    This is a utility class for controlling automata with no ambiguity.
    """
    def __init__(self, subject=None,verb="",thing="",strings={},objects={}):
        self.subject=subject
        self.verb=verb
        self.verbThing=thing
        self.strings=strings
        self.objects=objects

    def indirectString(self,string):
        """see Sentence.indirectString
        """
        try:
            return self.strings[string]
        except:
            raise error.NoString(self.verbString(),string)

    def directObject(self):
        """see Sentence.directObject
        """
        return self.indirectObject('')

    def verbString(self):
        """see Sentence.verbString
        """
        return self.verb

    def indirectObject(self, string):
        """see Sentence.indirectObject
        """
        try:
            return self.objects[string]
        except:
            raise error.NoObject(self.indirectString(string))

class _Token:
    "(internal) token representation for sentences"
    def __init__(self,ttype,val,no):
        "(internal)"
        self.ttype=ttype
        self.value=val
        self.line=no
        
    def __repr__(self):
        "(internal)"
        return '< Token %s at %s >'%(repr((self.ttype,
                                           self.value,
                                           self.line)),
                                     hex(id(self)))

class _AutoThingSet(UserList.UserList):
    """(internal)
    This is an ordered set, which behaves mostly like a list.  It's easy to get
    into an inconsistent state, because the only method with "set" symantics is
    "append", but it's used in Sentence.
    """
    def __init__(self, verb):
        "(internal) initialize the set"
        UserList.UserList.__init__(self)
        self.appended = {}
        self.verb = verb
        
    def addThing(self, thing):
        """(internal) maybe append something to the set
        """
        if ((not self.appended.has_key(thing)) and hasattr(thing, 'autoverbs')
            and thing.autoverbs.has_key(self.verb)):
            self.append(thing)
            self.appended[thing] = None

class Sentence:
    """Represents a single typed phrase by the user.
    Sentences are of the form:
    
       verb [direct-object] [preposition indirect-object] [preposition indirect-object]...

    "In English every word can be verbed. Would that it were so in our
    programming languages."
        -- Alan Perlis, Epigram #59
    """

    def _resolve(self, thing, preposition):
        """(internal)
        """
        if not (thing in map (lambda z: z[1], self.candidates)):
            verb = thing.getVerb(self._verb, preposition)
            if verb:
                self.candidates.append((verb, thing, None))

    def _ambientResolve(self, thing):
        """(internal)
        """
        ambient = thing.getAmbient(self._verb)
        if ambient:
            self.candidates.append((ambient, thing, None))

    def _abilityResolve(self, thing):
        """(internal)
        """
        ability = thing.getAbility(self._verb)
        if ability:
            self.candidates.append((ability, thing, None))

    def _autoResolve(self, thing):
        """(internal)
        """
        preposition = thing.autoverbs[self._verb]
        verb = thing.getVerb(self._verb, preposition)
        if verb:
            self.candidates.append((verb, thing, preposition))


    def run(self):
        """Do the action represented by this sentence.
        """
        for verb, thing, xprep in self.candidates:
            self.verbThing = thing
            if xprep is not None:
                try:
                    self.indirectString(xprep)
                except error.NoString:
                    tn = thing.shortName(self.subject)
                    self.strings[xprep]=tn
                    self.objects[xprep]=thing
                    # The following line needs some thought:
                    self.subject.hears("(",xprep," the ",tn,")")
                    
                    # It's very difficult to figure out when the verb
                    # has decided to "go through with it" and it's
                    # committed to not raising an InappropriateVerb.
                    # One would suppose this would be the first time
                    # that the verb calls 'hears'... I suppose I
                    # should be intercepting that, somehow.  Since a
                    # player can only run one sentence at a time it
                    # would be possible to, but it seems somehow
                    # wrong.
                    
                else:
                    continue
            if len(self.objects) == 1:
                self.subject.antecedent = self.objects.values()[0]
            else:
                self.subject.antecedent = None
                
            try:
                return verb(self)
            except error.InappropriateVerb:
                pass # go on to the next verb.

            if xprep is not None:
                del self.strings[xprep]
                del self.objects[xprep]

        if len(self.ambiguities) == 0:
            raise error.NoVerb(self.verbString())
        else:
            raise self.ambiguities.values()[0]

    #### tokenization
        
    def eat(self, ttype, tstring, tokBegin, tokEnd, line):
        """(internal) eat a token, for tokenizer
        """
        if ttype in (tokenize.NUMBER, tokenize.STRING):
            try:
                value = eval(tstring)
            except OverflowError:
                # temporary hack for parsing Longs
                value = eval(tstring+'L')
        else:
            value=tstring
        
        if (self._neg):
            if type(value).__name__ in ('int', 'float', 'long'):
                value = -value
            else:
                self.tokens.append(self._neg)
            self._neg=None

        tkn = _Token(ttype,value,tokBegin[0])

        if value == '-':
            self._neg=tkn
            return
        if not ttype in self.ignored:
            self.tokens.append(tkn)

    def stringioize(self, string):
        """(internal)
        
        the following is really just a stupid hack to emulate the quirky
        behavior of the string tokenizer in java; it is a historical artifact
        that just isn't badly broken enough to require being removed yet.
        """
        self.tokens = []
        self._neg = None
        fd = StringIO.StringIO(string)
        tokenize.tokenize(fd.readline,self.eat)
        self.reset()
        sn = self.next()
        try:
            while sn.ttype != tokenize.ERRORTOKEN:
                sn = self.next()
            # this is the best part.  It works completely by accident.
            # After 3 tries, you end up with a """ on the end of your
            # string, which is a multi-line string -- the tokenizer
            # will throw an exception for that (god knows why it
            # doesn't throw an exception for an EOF in a single-line
            # string...)
            self.stringioize(string+'"')
        except:
            pass
        self.reset()
        
    def next(self):
        """(internal) get the next token
        """
        current=self.tokens[self.counter]
        self.counter=self.counter+1
        return current

    def backtrack(self):
        """(internal) go back one token
        """
        self.counter=self.counter-1

    def reset(self):
        """(internal) reset tokenizer
        """
        self.counter=0

    #### END HISTORICAL ARTIFACTS

    def __init__(self,istr,player):
        """Sentence(sentence-string, actor): parse a string
        """
        # merged in from tokenizer.py
        # self.tokens=[]
        # self.ignored=ignored
        
        self.ignored=(tokenize.INDENT,tokenize.DEDENT,
                      tokenize.NL,tokenize.NEWLINE)

        self._neg=None
        # tokenize(file.readline,self.eat)
        # self.reset()
        
        # merged in fron sentence.py
        self.stringioize(istr)
        prepositions=['into', 'in', 'on', 'out', 'off', 'to', 'at', 'from',
                      'through', 'except', 'with', 'by']
        
        # begin the parsing ritual
        self.strings={}
        prp=''
        self._verb = self.next().value
        try:
            # another refactoring to be done -- invert this loop so that the
            # pre-tokenization pass isn't necessary.
            while 1:
                tkn = self.next()
                longword = ''
                while (not tkn.value in prepositions):
                    tkv=str(tkn.value)
                    if longword and not tkn.ttype == tokenize.ENDMARKER:
                        tkv = ' ' + tkv
                    longword = longword + tkv
                    self.strings[prp] = longword
                    tkn = self.next()
                prp = tkn.value
            assert 0, 'unreachable code'
        # I expect that self.next() will eventually throw an
        # exception, so
        except:
            pass
        
        # This is here because there will always be some token after the first
        # word (even if it's ENDMARKER) so it gets counted as a direct object.
        # If there was no word there, we remove it.
        if self.strings.get('')=='':
            del self.strings['']
        # end sentence merged stuff
        # sentence.Sentence.__init__(self,istr)
        self.subject = player
        self.place = player.place
        self.objects = {}
        self.ambiguities = {}
        self.candidates = []
        if (hasattr(player,"restricted_verbs") and
            self.verbString() not in player.restricted_verbs):
            raise error.NoVerb(self.verbString())

        # go through the pre-separated list of words and check to see if any of
        # them refer to objects.
        for prep,word in self.strings.items():
            try:
                self.objects[prep] = player.locate(word)
            except error.Ambiguity, a:
                self.ambiguities[prep] = a
            except error.CantFind:
                # If I couldn't find it, then it must just be a string.
                pass

        # The default way to resolve a verb-word into a callable object is
        # fairly straightforward.
        #
        # (1) all surface locations that a player is in, outermost first
        #     (meaning, if a player is sitting in a chair on top of a table
        #     inside a submarine in the sea, this will search chair, table,
        #     submarine) will be searched for methods of the form
        #     ambient_verbname.
        # 
        # (2) objects specified in the sentence explicitly will be searched for
        #     methods the form verb_verbname_preposition, where preposition is
        #     the preposition that the object being searched was found after in
        #     the sentence.
        # 
        # (3) the player will be searched for methods of the form
        #     ability_verbname.
        
        # (1) locations
        locations = list(player.locations)
        locations.reverse()
        for loc in locations:
            self._ambientResolve(loc)
        # (2) explicitly specified objects
        obVals = self.objects.items()
        obVals.sort() # sort by preposition name
        for prep, ob in obVals:
            if reflect.isinst(ob, thing.Thing):
                self._resolve(ob, prep)
        # (3) attempt to get an ability from the player
        self._abilityResolve(player)
        if self.candidates:
            return
        
        # If there are no candidates after scanning all of the usual suspects
        # for applicable verbs, perform an exhaustive search for other objects
        # which contain an auto-verb listed for this verb.  This means a
        # hashtable of the form
        #
        #   {verb: preposition,
        #    ...}
        # 
        # Where verb is the name of the verb which should be automatically used
        # and the preposition is the point in the sentence at which the thing
        # that the auto-verb was found upon will be inserted into the sentence.
        # 
        # This has the following order:
        #
        #  (1) The locations that the player is in, starting from the topmost
        #      location and cascading back to their immediate location.
        #  (2) The contents of each of those locations, in turn.
        #  (3) The player's focus.
        #  (4) All objects in the player's focus.
        #  (5) All objects that the player is holding.
        #  (6) The player themselves (this is for completeness, but I can't
        #      think of a reason off the top of my head why a player would ever
        #      contain an autoverb rather than an ability.)
        # 
        # If any object is found twice, it is searched the first time it's
        # found and not again.  Only objects that are visibile to the player
        # will be searched when searching the contents of an object.
        #
        # The following sections where each of these 6 things are added to the
        # resolve list are commented appropriately.

        # (0) set up some initial state
        autoThings = _AutoThingSet(self.verbString())
        # (1) the list of locations
        locs = list(player.locations)
        locs.reverse()
        for loc in locs:
            autoThings.addThing(loc)
        # (2) the contents of those locations
        for loc in locs:
            for obj in loc.getVisibleThings(player):
                autoThings.addThing(obj)
        # (3) the player's focus.
        focus = player.focus
        if focus is not None:
            autoThings.addThing(focus)
            # (4) All objects in the player's focus.
            for obj in focus.getVisibleThings(player):
                autoThings.addThing(obj)
        # (5) all objects that the player is holding.
        for obj in player.getVisibleThings(player):
            autoThings.addThing(obj)
        # (6) the player themselves
        autoThings.addThing(player)
        for thng in autoThings:
            self._autoResolve(thng)
            
        #for i in string.split(self.logAllParts(),'\n'):
        #    player.hears(i)
        
    def hasIndirect(self, preposition):
        return self.strings.has_key(preposition)
    
    def hasDirect(self):
        return self.hasIndirect('')
    
    def indirectString(self, preposition, default='_  _'):
        x = self.strings.get(preposition, default)
        if x != '_  _':
            return x
        
        raise error.NoString(self.verbString(),preposition)
        
    def directString(self, default='_  _'):
        return self.indirectString('', default)
    
    def verbString(self):
        """Sentence.verbString() -> String
        
        This returns the string that specifies this sentence's verb.  In a
        sentence like 'say hello', it is the string 'say'.
        """
        return self._verb

    def directObject(self, default='_  _'):
        """Sentence.directObject([default]) -> thing or default
        
        This returns the direct object of a sentence.  In a sentence like
        'shoot bob with gun', this would be the Player object representing Bob.

        If you do not specify the (optional) default object to return, this
        will raise an exception if a direct object cannot be supplied.

        raises: when no direct object was specified, error.NoString
                when a string was specified but it does not represent a valid
                Thing, error.NoObject.
        """

        return self.indirectObject('', default)

    def indirectObject(self, preposition, default='_  _'):
        x = self.ambiguities.get(preposition)
        if x:
            raise x
        x = self.objects.get(preposition)
        if x:
            return x
        
        if default != '_  _':
            return default
            
        raise error.NoObject(self.indirectString(preposition))


    def shouldOnlyHave(self, *prepositions):
        """Sentence.shouldOnlyHave(*list of prepositions)
        
        This method asserts that the only prepositions specified by this
        sentence are the ones in the argument list.  If any others are found,
        it will raise a TooManyObjects with an appropriately formatted message.
        (This is the only method which should ever raise TooManyObjects.)

        This is useful to be a little extra paranoid about `accidental
        dispatch', so that a verb can't be invoked by putting an object with it
        on it in the wrong place in a sentence.

        It will, therefore, succeed if some of the prepositions specified are
        *missing*; those will presumably be caught by later calls to
        indirectObject(...).
        """
        
        objects = copy.copy(self.objects)
        for preposition in prepositions:
            if objects.has_key(preposition):
                del objects[preposition]
        if objects:
            err = ["I only understood you so far as wanting to ",
                   self.verbString()]
            if self.hasDirect():
                err.append(" ")
                err.append(self.directObject())
                prepositions = list(prepositions)
                prepositions.remove('')
            for preposition in prepositions:
                err.append(" ")
                err.append(preposition)
                err.append(" ")
                err.append(self.indirectObject(preposition))
            err.append('.')
            raise apply(error.TooManyObjects, err)


    def logAllParts(self):
        x="*** Sentence ***\n"
        x=x+" verb [%s]\n" % self._verb
        x=x+" --- Objects ---\n"
        for prep,obj in self.objects.items():
            x=x+ "  [%s]: [%s]\n" % (prep, obj)
        x=x+ " --- Strings ---\n"
        for prep,name in self.strings.items():
            x=x+ "  [%s]: [%s]\n" % (prep, name)
        x=x+ " --- Ambiguities ---\n"
        for prep,name in self.ambiguities.items():
            x=x+ "  [%s]: [%s]\n" % (prep, name)
        return x
