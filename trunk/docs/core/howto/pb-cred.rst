
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Authentication with Perspective Broker
======================================








Overview
--------



The examples shown in :doc:`Using Perspective Broker <pb-usage>` demonstrate how to do basic remote method calls, but provided no
facilities for authentication. In this context, authentication is about who
gets which remote references, and how to restrict access to the "right" 
set of people or programs.




As soon as you have a program which offers services to multiple users,
where those users should not be allowed to interfere with each other, you
need to think about authentication. Many services use the idea of an "account" , and rely upon fact that each user has access to only one
account. Twisted uses a system called :doc:`cred <cred>` to
handle authentication issues, and Perspective Broker has code to make it
easy to implement the most common use cases.





Compartmentalizing Services
---------------------------



Imagine how you would write a chat server using PB. The first step might
be a ``ChatServer`` object which had a bunch of 
``pb.RemoteReference`` s that point at user clients. Pretend that
those clients offered a ``remote_print`` method which lets the
server print a message on the user's console. In that case, the server might
look something like this:





.. code-block:: python

    
    class ChatServer(pb.Referenceable):
    
        def __init__(self):
            self.groups = {} # indexed by name
            self.users = {} # indexed by name
        def remote_joinGroup(self, username, groupname):
            if not self.groups.has_key(groupname):
                self.groups[groupname] = []
            self.groups[groupname].append(self.users[username])
        def remote_sendMessage(self, from_username, groupname, message):
            group = self.groups[groupname]
            if group:
                # send the message to all members of the group
                for user in group:
                    user.callRemote("print",
                                    "<%s> says: %s" % (from_username,
                                                             message))




For now, assume that all clients have somehow acquired a 
``pb.RemoteReference`` to this ``ChatServer`` object,
perhaps using ``pb.Root`` and ``getRootObject`` as
described in the :doc:`previous chapter <pb-usage>` . In this
scheme, when a user sends a message to the group, their client runs
something like the following:





.. code-block:: python

    
    remotegroup.callRemote("sendMessage", "alice", "Hi, my name is alice.")






Incorrect Arguments
~~~~~~~~~~~~~~~~~~~



You've probably seen the first problem: users can trivially spoof each
other. We depend upon the user to pass a correct value in their
"username" argument, and have no way to tell if they're lying or not.
There is nothing to prevent Alice from modifying her client to do:





.. code-block:: python

    
    remotegroup.callRemote("sendMessage", "bob", "i like pork")




much to the horror of Bob's vegetarian friends. [#]_ 




(In general, learn to get suspicious if you see any argument of a
remotely-invokable method described as "must be X" )




The best way to fix this is to keep track of the user's name locally,
rather than asking them to send it to the server with each message. The best
place to keep state is in an object, so this suggests we need a per-user
object. Rather than choosing an obvious name [#]_ , let's call this the 
``User`` class.





.. code-block:: python

    
    class User(pb.Referenceable):
        def __init__(self, username, server, clientref):
            self.name = username
            self.server = server
            self.remote = clientref
        def remote_joinGroup(self, groupname):
            self.server.joinGroup(groupname, self)
        def remote_sendMessage(self, groupname, message):
            self.server.sendMessage(self.name, groupname, message)
        def send(self, message):
            self.remote.callRemote("print", message)
    
    class ChatServer:
        def __init__(self):
            self.groups = {} # indexed by name
        def joinGroup(self, groupname, user):
            if not self.groups.has_key(groupname):
                self.groups[groupname] = []
            self.groups[groupname].append(user)
        def sendMessage(self, from_username, groupname, message):
            group = self.groups[groupname]
            if group:
                # send the message to all members of the group
                for user in group:
                    user.send("<%s> says: %s" % (from_username, message))




Again, assume that each remote client gets access to a single 
``User`` object, which is created with the proper username.




Note how the ``ChatServer`` object has no remote access: it
isn't even ``pb.Referenceable`` anymore. This means that all access
to it must be mediated through other objects, with code that is under your
control.




As long as Alice only has access to her own ``User`` object, she
can no longer spoof Bob. The only way for her to invoke 
``ChatServer.sendMessage`` is to call her ``User`` 
object's ``remote_sendMessage`` method, and that method uses its
own state to provide the ``from_username`` argument. It doesn't
give her any way to change that state.




This restriction is important. The ``User`` object is able to
maintain its own integrity because there is a wall between the object and
the client: the client cannot inspect or modify internal state, like the 
``.name`` attribute. The only way through this wall is via remote
method invocations, and the only control Alice has over those invocations is
when they get invoked and what arguments they are given.



.. note::
   
   
   No object can maintain its integrity against local threats: by design,
   Python offers no mechanism for class instances to hide their attributes, and
   once an intruder has a copy of ``self.__dict__`` , they can do
   everything the original object was able to do.
   
   






Unforgeable References
~~~~~~~~~~~~~~~~~~~~~~



Now suppose you wanted to implement group parameters, for example a mode
in which nobody was allowed to talk about mattresses because some users were
sensitive and calming them down after someone said "mattress" is a
hassle that's best avoided altogether. Again, per-group state implies a
per-group object. We'll go out on a limb and call this the 
``Group`` object:





.. code-block:: python

    
    class User(pb.Referenceable):
        def __init__(self, username, server, clientref):
            self.name = username
            self.server = server
            self.remote = clientref
        def remote_joinGroup(self, groupname, allowMattress=True):
            return self.server.joinGroup(groupname, self, allowMattress)
        def send(self, message):
            self.remote.callRemote("print", message)
    
    class Group(pb.Referenceable):
        def __init__(self, groupname, allowMattress):
            self.name = groupname
            self.allowMattress = allowMattress
            self.users = []
        def remote_send(self, from_user, message):
            if not self.allowMattress and "mattress" in message:
                raise ValueError, "Don't say that word"
            for user in self.users:
                user.send("<%s> says: %s" % (from_user.name, message))
        def addUser(self, user):
            self.users.append(user)
    
    class ChatServer:
        def __init__(self):
            self.groups = {} # indexed by name
        def joinGroup(self, groupname, user, allowMattress):
            if groupname not in self.groups:
                self.groups[groupname] = Group(groupname, allowMattress)
            self.groups[groupname].addUser(user)
            return self.groups[groupname]





This example takes advantage of the fact that 
``pb.Referenceable`` objects sent over a wire can be returned to
you, and they will be turned into references to the same object that you
originally sent. The client cannot modify the object in any way: all they
can do is point at it and invoke its ``remote_*`` methods. Thus,
you can be sure that the ``.name`` attribute remains the same as
you left it. In this case, the client code would look something like
this:





.. code-block:: python

    
    class ClientThing(pb.Referenceable):
        def remote_print(self, message):
            print message
        def join(self):
            d = self.remoteUser.callRemote("joinGroup", "#twisted",
                                           allowMattress=False)
            d.addCallback(self.gotGroup)
        def gotGroup(self, group):
            group.callRemote("send", self.remoteUser, "hi everybody")




The ``User`` object is sent from the server side, and is turned
into a ``pb.RemoteReference`` when it arrives at the client. The
client sends it back to ``Group.remote_send`` , and PB turns it back
into a reference to the original ``User`` when it gets there. 
``Group.remote_send`` can then use its ``.name`` attribute
as the sender of the message.



.. note::
   
   
   
   Third party references (there aren't any)
   
   
   
   
   This technique also relies upon the fact that the 
   ``pb.Referenceable`` reference can *only* come from someone
   who holds a corresponding ``pb.RemoteReference`` . The design of the
   serialization mechanism (implemented in :api:`twisted.spread.jelly <twisted.spread.jelly>` : pb, jelly, spread.. get it?  Look for "banana" , too.  What other networking framework
   can claim API names based on sandwich ingredients?) makes it impossible for
   a client to obtain a reference that they weren't explicitly given.
   References passed over the wire are given id numbers and recorded in a
   per-connection dictionary. If you didn't give them the reference, the id
   number won't be in the dict, and no amount of guessing by a malicious client
   will give them anything else. The dict goes away when the connection is
   dropped, further limiting the scope of those references.
   
   
   
   
   Furthermore, it is not possible for Bob to send *his* 
   ``User`` reference to Alice (perhaps over some other PB channel
   just between the two of them). Outside the context of Bob's connection to
   the server, that reference is just a meaningless number. To prevent
   confusion, PB will tell you if you try to give it away: when you try to hand
   a ``pb.RemoteReference`` to a third party, you'll get an exception
   (implemented with an assert in pb.py:364 RemoteReference.jellyFor).
   
   
   
   
   This helps the security model somewhat: only the client you gave the
   reference to can cause any damage with it. Of course, the client might be a
   brainless zombie, simply doing anything some third party wants. When it's
   not proxying ``callRemote`` invocations, it's probably terrorizing
   the living and searching out human brains for sustenance. In short, if you
   don't trust them, don't give them that reference.
   
   
   
   
   And remember that everything you've ever given them over that connection
   can come back to you. If expect the client to invoke your method with some
   object A that you sent to them earlier, and instead they send you object B
   (that you also sent to them earlier), and you don't check it somehow, then
   you've just opened up a security hole (we'll see an example of this
   shortly). It may be better to keep such objects in a dictionary on the
   server side, and have the client send you an index string instead. Doing it
   that way makes it obvious that they can send you anything they want, and
   improves the chances that you'll remember to implement the right checks.
   (This is exactly what PB is doing underneath, with a per-connection
   dictionary of ``Referenceable`` objects, indexed by a number).
   
   
   
   
   And, of course, you have to make sure you don't accidentally hand out a
   reference to the wrong object.
   
   
   





But again, note the vulnerability. If Alice holds a 
``RemoteReference`` to *any* object on the server side that
has a ``.name`` attribute, she can use that name as a spoofed"from" parameter. As a simple example, what if her client code looked
like:





.. code-block:: python

    
    class ClientThing(pb.Referenceable):
        def join(self):
            d = self.remoteUser.callRemote("joinGroup", "#twisted")
            d.addCallback(self.gotGroup)
        def gotGroup(self, group):
            group.callRemote("send", from_user=group, "hi everybody")




This would let her send a message that appeared to come from "#twisted" rather than "Alice" . If she joined a group that
happened to be named "bob" (perhaps it is the "How To Be Bob" 
channel, populated by Alice and countless others, a place where they can
share stories about their best impersonating-Bob moments), then she would be
able to emit a message that looked like "<bob> says: hi there" ,
and she has accomplished her lifelong goal.






Argument Typechecking
~~~~~~~~~~~~~~~~~~~~~



There are two techniques to close this hole. The first is to have your
remotely-invokable methods do type-checking on their arguments: if 
``Group.remote_send`` asserted ``isinstance(from_user, User)`` then Alice couldn't use non-User objects to do her spoofing,
and hopefully the rest of the system is designed well enough to prevent her
from obtaining access to somebody else's User object.






Objects as Capabilities
~~~~~~~~~~~~~~~~~~~~~~~



The second technique is to avoid having the client send you the objects
altogether. If they don't send you anything, there is nothing to verify. In
this case, you would have to have a per-user-per-group object, in which the 
``remote_send`` method would only take a single 
``message`` argument. The ``UserGroup`` object is created
with references to the only ``User`` and ``Group`` objects
that it will ever use, so no lookups are needed:





.. code-block:: python

    
    class UserGroup(pb.Referenceable):
        def __init__(self, user, group):
            self.user = user
            self.group = group
        def remote_send(self, message):
            self.group.send(self.user.name, message)
    
    class Group:
        def __init__(self, groupname, allowMattress):
            self.name = groupname
            self.allowMattress = allowMattress
            self.users = []
        def send(self, from_user, message):
            if not self.allowMattress and "mattress" in message:
                raise ValueError, "Don't say that word"
            for user in self.users:
                user.send("<%s> says: %s" % (from_user.name, message))
        def addUser(self, user):
            self.users.append(user)




The only message-sending method Alice has left is 
``UserGroup.remote_send`` , and it only accepts a message: there are
no remaining ways to influence the "from" name.




In this model, each remotely-accessible object represents a very small
set of capabilities. Security is achieved by only granting a minimal set of
abilities to each remote user.




PB provides a shortcut which makes this technique easier to use. The 
``Viewable`` class will be discussed :ref:`below <core-howto-pb-cred-viewable>` .





Avatars and Perspectives
------------------------



In Twisted's :doc:`cred <cred>` system, an "Avatar" is
an object that lives on the "server" side (defined here as the side
farthest from the human who is trying to get something done) which lets the
remote user get something done. The avatar isn't really a particular class,
it's more like a description of a role that some object plays, as in "the Foo object here is acting as the user's avatar for this particular service" . Generally, the remote user has some way of getting their avatar
to run some code. The avatar object may enforce some security checks, and
provide additional data, then call other methods which get things done.




The two pieces in the cred puzzle (for any protocol, not just PB) are: "what serves as the Avatar?" , and "how does the user get access to it?" .




For PB, the first question is easy. The Avatar is a remotely-accessible
object which can run code: this is a perfect description of 
``pb.Referenceable`` and its subclasses. We shall defer the second
question until the next section.




In the example above, you can think of the ``ChatServer`` and 
``Group`` objects as a service. The ``User`` object is the
user's server-side representative: everything the user is capable of doing
is done by running one of its methods. Anything that the server wants to do
to the user (change their group membership, change their name, delete their
pet cat, whatever) is done by manipulating the ``User`` object.




There are multiple User objects living in peace and harmony around the
ChatServer. Each has a different point of view on the services provided by
the ChatServer and the Groups: each may belong to different groups, some
might have more permissions than others (like the ability to create groups).
These different points of view are called "Perspectives" . This is the
origin of the term "Perspective" in "Perspective Broker" : PB
provides and controls (i.e. "brokers" ) access to Perspectives.




Once upon a time, these local-representative objects were actually called 
``pb.Perspective`` . But this has changed with the advent of the
rewritten cred system, and now the more generic term for a local
representative object is an Avatar. But you will still see reference to
"Perspective" in the code, the docs, and the module names [#]_ . Just remember
that perspectives and avatars are basically the same thing. 




Despite all we've been :doc:`telling you <cred>` about how
Avatars are more of a concept than an actual class, the base class from
which you can create your server-side avatar-ish objects is, in fact, named 
``pb.Avatar``  [#]_ . These objects behave very much like 
``pb.Referenceable`` . The only difference is that instead of
offering "remote_FOO" methods, they offer "perspective_FOO" 
methods.




The other way in which ``pb.Avatar`` differs from 
``pb.Referenceable`` is that the avatar objects are designed to be
the first thing retrieved by a cred-using remote client. Just as 
``PBClientFactory.getRootObject`` gives the client access to a 
``pb.Root`` object (which can then provide access to all kinds of
other objects), ``PBClientFactory.login`` gives client access to a 
``pb.Avatar`` object (which can return other references). 




So, the first half of using cred in your PB application is to create an
Avatar object which implements ``perspective_`` methods and is
careful to do useful things for the remote user while remaining vigilant
against being tricked with unexpected argument values. It must also be
careful to never give access to objects that the user should not have access
to, whether by returning them directly, returning objects which contain
them, or returning objects which can be asked (remotely) to provide
them.




The second half is how the user gets a ``pb.RemoteReference`` to
your Avatar. As explained :doc:`elsewhere <cred>` , Avatars are
obtained from a Realm. The Realm doesn't deal with authentication at all
(usernames, passwords, public keys, challenge-response systems, retinal
scanners, real-time DNA sequencers, etc). It simply takes an "avatarID" 
(which is effectively a username) and returns an Avatar object. The Portal
and its Checkers deal with authenticating the user: by the time they are
done, the remote user has proved their right to access the avatarID that is
given to the Realm, so the Realm can return a remotely-controllable object
that has whatever powers you wish to grant to this particular user. 




For PB, the realm is expected to return a ``pb.Avatar`` (or
anything which implements ``pb.IPerspective`` , really, but there's
no reason to not return a ``pb.Avatar`` subclass). This object will
be given to the client just like a ``pb.Root`` would be without
cred, and the user can get access to other objects through it (if you let
them).




The basic idea is that there is a separate IPerspective-implementing
object (i.e. the Avatar subclass) (i.e. the "perspective" ) for each
user, and *only* the authorized user gets a remote reference to that
object. You can store whatever permissions or capabilities the user
possesses in that object, and then use them when the user invokes a remote
method. You give the user access to the perspective object instead of the
objects that do the real work.






Perspective Examples
--------------------



Here is a brief example of using a pb.Avatar. Most of the support code
is magic for now: we'll explain it later.





One Client
~~~~~~~~~~




:download:`pb5server.py <listings/pb/pb5server.py>`

.. literalinclude:: listings/pb/pb5server.py



:download:`pb5client.py <listings/pb/pb5client.py>`

.. literalinclude:: listings/pb/pb5client.py


Ok, so that wasn't really very exciting. It doesn't accomplish much more
than the first PB example, and used a lot more code to do it. Let's try it
again with two users this time.



.. note::
   
   
   
   When the client runs ``login`` to request the Perspective,
   they can provide it with an optional ``client`` argument (which
   must be a ``pb.Referenceable`` object). If they do, then a
   reference to that object will be handed to the realm's 
   ``requestAvatar`` in the ``mind`` argument.
   
   
   
   
   The server-side Perspective can use it to invoke remote methods on
   something in the client, so that the client doesn't always have to drive the
   interaction. In a chat server, the client object would be the one to which"display text" messages were sent. In a board game server, this would
   provide a way to tell the clients that someone has made a move, so they can
   update their game boards.
   
   
   





Two Clients
~~~~~~~~~~~




:download:`pb6server.py <listings/pb/pb6server.py>`

.. literalinclude:: listings/pb/pb6server.py



:download:`pb6client1.py <listings/pb/pb6client1.py>`

.. literalinclude:: listings/pb/pb6client1.py



:download:`pb6client2.py <listings/pb/pb6client2.py>`

.. literalinclude:: listings/pb/pb6client2.py


While pb6server.py is running, try starting pb6client1, then pb6client2.
Compare the argument passed by the ``.callRemote()`` in each
client. You can see how each client gets connected to a different
Perspective.






How that example worked
~~~~~~~~~~~~~~~~~~~~~~~
.. _core-howto-pb-cred-smallexample:








Let's walk through the previous example and see what was going on.




First, we created a subclass called ``MyPerspective`` which is
our server-side Avatar. It implements a ``perspective_foo`` method
that is exposed to the remote client.




Second, we created a realm (an object which implements 
``IRealm`` , and therefore implements ``requestAvatar`` ).
This realm manufactures ``MyPerspective`` objects. It makes as many
as we want, and names each one with the avatarID (a username) that comes out
of the checkers. This MyRealm object returns two other objects as well,
which we will describe later.




Third, we created a portal to hold this realm. The portal's job is to
dispatch incoming clients to the credential checkers, and then to request
Avatars for any which survive the authentication process.




Fourth, we made a simple checker (an object which implements 
``IChecker`` ) to hold valid user/password pairs. The checker
gets registered with the portal, so it knows who to ask when new
clients connect.  We use a checker named 
``InMemoryUsernamePasswordDatabaseDontUse`` , which suggests
that 1: all the username/password pairs are kept in memory instead of
being saved to a database or something, and 2: you shouldn't use
it. The admonition against using it is because there are better
schemes: keeping everything in memory will not work when you have
thousands or millions of users to keep track of, the passwords will be
stored in the .tap file when the application shuts down (possibly a
security risk), and finally it is a nuisance to add or remove users
after the checker is constructed.




Fifth, we create a ``pb.PBServerFactory`` to listen on a TCP
port. This factory knows how to connect the remote client to the Portal, so
incoming connections will be handed to the authentication process. Other
protocols (non-PB) would do something similar: the factory that creates
Protocol objects will give those objects access to the Portal so
authentication can take place.




On the client side, a ``pb.PBClientFactory`` is created (as :doc:`before <pb-usage>` ) and attached to a TCP connection. When the
connection completes, the factory will be asked to produce a Protocol, and
it will create a PB object. Unlike the previous chapter, where we used 
``.getRootObject`` , here we use ``factory.login`` to
initiate the cred authentication process. We provide a 
``credentials`` object, which is the client-side agent for doing
our half of the authentication process. This process may involve several
messages: challenges, responses, encrypted passwords, secure hashes, etc. We
give our credentials object everything it will need to respond correctly (in
this case, a username and password, but you could write a credential that
used public-key encryption or even fancier techniques).




``login`` returns a Deferred which, when it fires, will return a 
``pb.RemoteReference`` to the remote avatar. We can then do 
``callRemote`` to invoke a ``perspective_foo`` method on
that Avatar.






Anonymous Clients
~~~~~~~~~~~~~~~~~




:download:`pbAnonServer.py <listings/pb/pbAnonServer.py>`

.. literalinclude:: listings/pb/pbAnonServer.py



:download:`pbAnonClient.py <listings/pb/pbAnonClient.py>`

.. literalinclude:: listings/pb/pbAnonClient.py


pbAnonServer.py implements a server based on pb6server.py, extending it to
permit anonymous logins in addition to authenticated logins. An 
:api:`twisted.cred.checkers.AllowAnonymousAccess <AllowAnonymousAccess>` 
checker and an :api:`twisted.cred.checkers.InMemoryUsernamePasswordDatabaseDontUse <InMemoryUsernamePasswordDatabaseDontUse>` 
checker are registered and the
client's choice of credentials object determines which is used to authenticate
the login.  In either case, the realm will be called on to create an avatar for
the login.  ``AllowAnonymousAccess`` always produces an ``avatarId`` of ``twisted.cred.checkers.ANONYMOUS`` .




On the client side, the only change is the use of an instance of 
:api:`twisted.cred.credentials.Anonymous <Anonymous>` when calling 
:api:`twisted.spread.pb.PBClientFactory.login <PBClientFactory.login>` .






Using Avatars
-------------





Avatar Interfaces
~~~~~~~~~~~~~~~~~



The first element of the 3-tuple returned by ``requestAvatar`` 
indicates which Interface this Avatar implements. For PB avatars, it will
always be ``pb.IPerspective`` , because that's the only interface
these avatars implement.




This element is present because ``requestAvatar`` is actually
presented with a list of possible Interfaces. The question being posed to
the Realm is: "do you have an avatar for (avatarID) that can implement one of the following set of Interfaces?" . Some portals and checkers might
give a list of Interfaces and the Realm could pick; the PB code only knows
how to do one, so we cannot take advantage of this feature.





Logging Out
~~~~~~~~~~~



The third element of the 3-tuple is a zero-argument callable, which will
be invoked by the protocol when the connection has been lost. We can use
this to notify the Avatar when the client has lost its connection. This will
be described in more detail below.





Making Avatars
~~~~~~~~~~~~~~



In the example above, we create Avatars upon request, during 
``requestAvatar`` . Depending upon the service, these Avatars might
already exist before the connection is received, and might outlive the
connection. The Avatars might also accept multiple connections.




Another possibility is that the Avatars might exist ahead of time, but in
a different form (frozen in a pickle and/or saved in a database). In this
case, ``requestAvatar`` may need to perform a database lookup and
then do something with the result before it can provide an avatar. In this
case, it would probably return a Deferred so it could provide the real
Avatar later, once the lookup had completed.




Here are some possible implementations of 
``MyRealm.requestAvatar`` :





.. code-block:: python

    
    # pre-existing, static avatars
    def requestAvatar(self, avatarID, mind, *interfaces):
        assert pb.IPerspective in interfaces
        avatar = self.avatars[avatarID]
        return pb.IPerspective, avatar, lambda:None
    
    # database lookup and unpickling
    def requestAvatar(self, avatarID, mind, *interfaces):
        assert pb.IPerspective in interfaces
        d = self.database.fetchAvatar(avatarID)
        d.addCallback(self.doUnpickle)
        return pb.IPerspective, d, lambda:None
    def doUnpickle(self, pickled):
        avatar = pickle.loads(pickled)
        return avatar
    
    # everybody shares the same Avatar
    def requestAvatar(self, avatarID, mind, *interfaces):
        assert pb.IPerspective in interfaces
        return pb.IPerspective, self.theOneAvatar, lambda:None
    
    # anonymous users share one Avatar, named users each get their own
    def requestAvatar(self, avatarID, mind, *interfaces):
        assert pb.IPerspective in interfaces
        if avatarID == checkers.ANONYMOUS:
            return pb.IPerspective, self.anonAvatar, lambda:None
        else:
            return pb.IPerspective, self.avatars[avatarID], lambda:None
    
    # anonymous users get independent (but temporary) Avatars
    # named users get their own persistent one
    def requestAvatar(self, avatarID, mind, *interfaces):
        assert pb.IPerspective in interfaces
        if avatarID == checkers.ANONYMOUS:
            return pb.IPerspective, MyAvatar(), lambda:None
        else:
            return pb.IPerspective, self.avatars[avatarID], lambda:None




The last example, note that the new ``MyAvatar`` instance is not
saved anywhere: it will vanish when the connection is dropped. By contrast,
the avatars that live in the ``self.avatars`` dictionary will
probably get persisted into the .tap file along with the Realm, the Portal,
and anything else that is referenced by the top-level Application object.
This is an easy way to manage saved user profiles.






Connecting and Disconnecting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~



It may be useful for your Avatars to be told when remote clients gain
(and lose) access to them. For example, and Avatar might be updated by
something in the server, and if there are clients attached, it should update
them (through the "mind" argument which lets the Avatar do callRemote
on the client).




One common idiom which accomplishes this is to have the Realm tell the
avatar that a remote client has just attached. The Realm can also ask the
protocol to let it know when the connection goes away, so it can then inform
the Avatar that the client has detached. The third member of the 
``requestAvatar`` return tuple is a callable which will be invoked
when the connection is lost.





.. code-block:: python

    
    class MyPerspective(pb.Avatar):
        def __init__(self):
            self.clients = []
        def attached(self, mind):
            self.clients.append(mind)
            print "attached to", mind
        def detached(self, mind):
            self.clients.remove(mind)
            print "detached from", mind
        def update(self, message):
            for c in self.clients:
                c.callRemote("update", message)
    
    class MyRealm:
        def requestAvatar(self, avatarID, mind, *interfaces):
            assert pb.IPerspective in interfaces
            avatar = self.avatars[avatarID]
            avatar.attached(mind)
            return pb.IPerspective, avatar, lambda a=avatar:a.detached(mind)






Viewable
~~~~~~~~
 .. _core-howto-pb-cred-viewable:








Once you have ``IPerspective`` objects (i.e. the Avatar) to
represent users, the :api:`twisted.spread.pb.Viewable <Viewable>` class can come into play. This
class behaves a lot like ``Referenceable`` : it turns into a 
``RemoteReference`` when sent over the wire, and certain methods
can be invoked by the holder of that reference. However, the methods that
can be called have names that start with ``view_`` instead of  ``remote_`` , and those methods are always called with an extra ``perspective`` argument that points to the Avatar through which
the reference was sent:





.. code-block:: python

    
    class Foo(pb.Viewable):
        def view_doFoo(self, perspective, arg1, arg2):
            pass




This is useful if you want to let multiple clients share a reference to
the same object. The ``view_`` methods can use the
"perspective" argument to figure out which client is calling them. This
gives them a way to do additional permission checks, do per-user accounting,
etc.




This is the shortcut which makes per-user-per-group capability objects
much easier to use. Instead of creating such per-(user,group) objects, you
just have per-group objects which inherit from ``pb.Viewable`` , and
give the user references to them. The local ``pb.Avatar`` object
will automatically show up as the "perspective" argument in the
``view_*`` method calls, give you a chance to involve the Avatar in
the process.






Chat Server with Avatars
~~~~~~~~~~~~~~~~~~~~~~~~



Combining all the above techniques, here is an example chat server which
uses a fixed set of identities (say, for the three members of your bridge
club, who hang out in "#NeedAFourth" hoping that someone will discover
your server, guess somebody's password, break in, join the group, and also
be available for a game next Saturday afternoon).





:download:`chatserver.py <listings/pb/chatserver.py>`

.. literalinclude:: listings/pb/chatserver.py


Notice that the client uses ``perspective_joinGroup`` to both
join a group and retrieve a ``RemoteReference`` to the
``Group`` object. However, the reference they get is actually to a
special intermediate object called a ``pb.ViewPoint`` . When they do
``group.callRemote("send", "message")`` , their avatar is inserted
into the argument list that ``Group.view_send`` actually sees. This
lets the group get their username out of the Avatar without giving the
client an opportunity to spoof someone else.




The client side code that joins a group and sends a message would look
like this:





:download:`chatclient.py <listings/pb/chatclient.py>`

.. literalinclude:: listings/pb/chatclient.py



.. rubric:: Footnotes

.. [#] Apparently Alice is one of those weirdos who has nothing
       better to do than to try and impersonate Bob. She will lie to her chat
       client, send incorrect objects to remote methods, even rewrite her local
       client code entirely to accomplish this juvenile prank. Given this
       adversarial relationship, one must wonder why she and Bob seem to spend so
       much time together: their adventures are clearly documented by the
       cryptographic literature.
.. [#] The
       obvious name is clearly 
       ``ServerSidePerUserObjectWhichNobodyElseHasAccessTo`` , but because
       Python makes everything else so easy to read, it only seems fair to make
       your audience work for *something* .
.. [#] We could just go ahead and rename Perspective Broker to be
       Avatar Broker, but 1) that would cause massive compatibility problems, and 2) 
       "AB"  doesn't fit into the whole sandwich-themed naming scheme nearly as
       well as "PB"  does. If we changed it to AB, we'd probably have to change
       Banana to be CD (CoderDecoder), and Jelly to be EF (EncapsulatorFragmentor).
       twisted.spread would then have to be renamed twisted.alphabetsoup, and then
       the whole food-pun thing would start all over again.
.. [#] The avatar-ish class is named 
       ``pb.Avatar``  because ``pb.Perspective``  was already
       taken, by the (now obsolete) oldcred perspective-ish class. It is a pity,
       but it simply wasn't possible both replace ``pb.Perspective`` 
       in-place *and*  maintain a reasonable level of
       backwards-compatibility.
