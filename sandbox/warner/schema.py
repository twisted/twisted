

"""

RemoteReference objects should all be tagged with interfaces that they
implement, which point to representations of the method schemas.  When a remote
method is called, PB should look up the appropriate method and serialize the
argument list accordingly.

We plan to eliminate positional arguments, so local RemoteReferences use their
schema to convert callRemote calls with positional arguments to all-keyword
arguments before serialization.

Conversion to the appropriate version interface should be handled at the
application level.  Eventually, with careful use of twisted.python.context, we
might be able to provide automated tools for helping application authors
automatically convert interface calls and isolate version-conversion code, but
that is probably pretty hard.

"""


class Attributes:
    def __init__(self,*a,**k):
        pass

X = Attributes(
    ('hello', str),
    ('goodbye', int),
    ('next', Narf),
    ('asdf', ListOf(Narf, maxLength=30)),
    ('fdsa', (Narf, String(maxLength=5), int)),
    ('qqqq', DictOf(str, Narf)),
    ('larg', AttributeDict(('A', int),
                           ('X', Number),
                           ('Z', float))),
    Optional("foo", str),
    Optional("bar", str, default=None),
    ignoreUnknown=True,
    )


class Narf(Remoteable):
    # step 1
    __schema__ = X
    # step 2 (possibly - this loses information)
    class schema:
        hello = str
        goodbye = int
        class add:
            x = Number
            y = Number
            __return__ = Copy(Number)

        class getRemoteThingy:
            fooID = Arg(WhateverID, default=None)
            barID = Arg(WhateverID, default=None)
            __return__ = Reference(Narf)

    # step 3
    schema = """
    int add (int a, int b)
    """

    # Since the above schema could also be used for Formless, or possibly for
    # World (for state) we can also do:

    class remote_schema:
        """blah blah
        """

    # You could even subclass that from the other one...

    class remote_schema(schema):
        dontUse = 'hello', 'goodbye'

            
    def remote_add(self, x, y):
        return x + y

    def rejuvinate(self, deadPlayer):
        return Reference(deadPlayer.bringToLife())

    # "Remoteable" is a new concept - objects which may be method-published
    # remotely _or_ copied remotely.  The schema objects support both method /
    # interface definitions and state definitions, so which one gets used can
    # be defined by the sending side as to whether it sends a
    # Copy(theRemoteable) or Reference(theRemoteable)

    # (also, with methods that are explicitly published by a schema there is no
    # longer technically any security need for the remote_ prefix, which, based
    # on past experience can be kind of annoying if you want to provide the
    # same methods locally and remotely)

    # outstanding design choice - Referenceable and Copyable are subclasses of
    # Remoteable, but should they restrict the possibility of sending it the
    # other way or 

    def getPlayerInfo(self, playerID):
        return Copy(self.players[playerID])

    def getRemoteThingy(self, fooID, barID):
        return Reference(self.players[selfPlayerID])


class RemoteNarf(Remoted):
    __schema__ = X
    # or, example of a difference between local and remote
    class schema:
        class getRemoteThingy:
            __return__ Reference(RemoteNarf)

## (and yes, donovan, we know that TypedInterface exists and we are going to
## use it.  we're just screwing around with other syntaxes to see what about PB
## might be different.)
