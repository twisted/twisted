
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Managing Clients of Perspectives
================================






:Author: Kevin Turner



Overview
--------



In all the :py:class:`IPerspective <twisted.spread.pb.IPerspective>` uses
we have shown so far, we ignored the ``mind`` argument and created
a new ``Avatar`` for every connection. This is usually an easy
design choice, and it works well for simple cases.




In more complicated cases, for example an ``Avatar`` that
represents a player object which is persistent in the game universe,
we will want connections from the same player to use the same ``Avatar`` .




Another thing which is necessary in more complicated scenarios
is notifying a player asynchronously. While it is possible, of
course, to allow a player to call ``perspective_remoteListener(referencable)`` that would
mean both duplication of code and a higher latency in logging in,
both bad.




In previous sections all realms looked to be identical.
In this one we will show the usefulness of realms in accomplishing
those two objectives.





Managing Avatars
----------------



The simplest way to manage persistent avatars is to use a straight-forward
caching mechanism:





.. code-block:: python

    
    from zope.interface import implementer
    
    class SimpleAvatar(pb.Avatar):
        greetings = 0
        def __init__(self, name):
            self.name = name
        def perspective_greet(self):
            self.greetings += 1
            return "<%d>hello %s" % (self.greetings, self.name)
    
    @implementer(portal.IRealm)
    class CachingRealm:
    
        def __init__(self):
            self.avatars = {}
    
        def requestAvatar(self, avatarId, mind, *interfaces):
            if pb.IPerspective not in interfaces: raise NotImplementedError
            if avatarId in self.avatars:
                p = self.avatars[avatarId]
            else:
                p = self.avatars[avatarId] = SimpleAvatar(avatarId)
            return pb.IPerspective, p, lambda:None




This gives us a perspective which counts the number of greetings it
sent its client. Implementing a caching strategy, as opposed to generating
a realm with the correct avatars already in it, is usually easier. This
makes adding new checkers to the portal, or adding new users to a checker
database, transparent. Otherwise, careful synchronization is needed between
the checker and avatar is needed (much like the synchronization between
UNIX's ``/etc/shadow`` and ``/etc/passwd`` ).




Sometimes, however, an avatar will need enough per-connection state
that it would be easier to generate a new avatar and cache something
else. Here is an example of that:





.. code-block:: python

    
    from zope.interface import implementer
    
    class Greeter:
        greetings = 0
        def hello(self):
            self.greetings += 1
            return "<%d>hello" % (self.greetings, self.name)
    
    class SimpleAvatar(pb.Avatar):
        def __init__(self, name, greeter):
            self.name = name
            self.greeter = greeter
        def perspective_greet(self):
            return self.greeter.hello()+' '+self.name
    
    @implementer(portal.IRealm)
    class CachingRealm:
        def __init__(self):
            self.greeters = {}
    
        def requestAvatar(self, avatarId, mind, *interfaces):
            if pb.IPerspective not in interfaces: raise NotImplementedError
            if avatarId in self.greeters:
                p = self.greeters[avatarId]
            else:
                p = self.greeters[avatarId] = Greeter()
            return pb.IPerspective, SimpleAvatar(avatarId, p), lambda:None




It might seem tempting to use this pattern to have an avatar which
is notified of new connections. However, the problems here are twofold:
it would lead to a thin class which needs to forward all of its methods,
and it would be impossible to know when disconnections occur. Luckily,
there is a better pattern:





.. code-block:: python

    
    from zope.interface import implementer
    
    class SimpleAvatar(pb.Avatar):
        greetings = 0
        connections = 0
        def __init__(self, name):
            self.name = name
        def connect(self):
            self.connections += 1
        def disconnect(self):
            self.connections -= 1
        def perspective_greet(self):
            self.greetings += 1
            return "<%d>hello %s" % (self.greetings, self.name)
    
    @implementer(portal.IRealm)
    class CachingRealm:
        def __init__(self):
            self.avatars = {}
    
        def requestAvatar(self, avatarId, mind, *interfaces):
            if pb.IPerspective not in interfaces: raise NotImplementedError
            if avatarId in self.avatars:
                p = self.avatars[avatarId]
            else:
                p = self.avatars[avatarId] = SimpleAvatar(avatarId)
            p.connect()
            return pb.IPerspective, p, p.disconnect




It is possible to use such a pattern to define an arbitrary limit for
the number of concurrent connections:





.. code-block:: python

    
    from zope.interface import implementer
    
    class SimpleAvatar(pb.Avatar):
        greetings = 0
        connections = 0
        def __init__(self, name):
            self.name = name
        def connect(self):
            self.connections += 1
        def disconnect(self):
            self.connections -= 1
        def perspective_greet(self):
            self.greetings += 1
            return "<%d>hello %s" % (self.greetings, self.name)
    
    @implementer(portal.IRealm)
    class CachingRealm:
        def __init__(self, max=1):
            self.avatars = {}
            self.max = max
    
        def requestAvatar(self, avatarId, mind, *interfaces):
            if pb.IPerspective not in interfaces: raise NotImplementedError
            if avatarId in self.avatars:
                p = self.avatars[avatarId]
            else:
                p = self.avatars[avatarId] = SimpleAvatar(avatarId)
            if p.connections >= self.max:
                raise ValueError("too many connections")
            p.connect()
            return pb.IPerspective, p, p.disconnect





Managing Clients
----------------



So far, all our realms have ignored the ``mind`` argument.
In the case of PB, the ``mind`` is an object supplied by
the remote login method -- usually, when it passes over the wire,
it becomes a ``pb.RemoteReference`` . This object allows
sending messages to the client as soon as the connection is established
and authenticated.




Here is a simple remote-clock application which shows the usefulness
of the ``mind`` argument:





.. code-block:: python

    
    from zope.interface import implementer
    
    class SimpleAvatar(pb.Avatar):
        def __init__(self, client):
            self.s = internet.TimerService(1, self.telltime)
            self.s.startService()
            self.client = client
        def telltime(self):
            self.client.callRemote("notifyTime", time.time())
        def perspective_setperiod(self, period):
            self.s.stopService()
            self.s = internet.TimerService(period, self.telltime)
            self.s.startService()
        def logout(self):
            self.s.stopService()
    
    @implementer(portal.IRealm)
    class Realm:
        def requestAvatar(self, avatarId, mind, *interfaces):
            if pb.IPerspective not in interfaces: raise NotImplementedError
            p = SimpleAvatar(mind)
            return pb.IPerspective, p, p.logout




In more complicated situations, you might want to cache the avatars
and give each one a set of "current clients" or something similar.



