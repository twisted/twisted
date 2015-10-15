
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Introduction to Perspective Broker
==================================







Introduction
------------



Suppose you find yourself in control of both ends of the wire: you
have two programs that need to talk to each other, and you get to use any
protocol you want. If you can think of your problem in terms of objects that
need to make method calls on each other, then chances are good that you can
use Twisted's Perspective Broker protocol rather than trying to shoehorn
your needs into something like HTTP, or implementing yet another RPC
mechanism [#]_ .




The Perspective Broker system (abbreviated "PB" , spawning numerous
sandwich-related puns) is based upon a few central concepts:







- *serialization* : taking fairly arbitrary objects and types,
  turning them into a chunk of bytes, sending them over a wire, then
  reconstituting them on the other end. By keeping careful track of object
  ids, the serialized objects can contain references to other objects and
  the remote copy will still be useful. 
- *remote method calls* : doing something to a local object and
  causing a method to get run on a distant one. The local object is called a
  :api:`twisted.spread.pb.RemoteReference <RemoteReference>` , and you
  "do something" by running its ``.callRemote`` method.





This document will contain several examples that will (hopefully) appear
redundant and verbose once you've figured out what's going on. To begin
with, much of the code will just be labelled "magic" : don't worry about how
these parts work yet. It will be explained more fully later.





Object Roadmap
--------------



To start with, here are the major classes, interfaces, and
functions involved in PB, with links to the file where they are
defined (all of which are under twisted/, of course). Don't worry
about understanding what they all do yet: it's easier to figure them
out through their interaction than explaining them one at a time.







- :api:`twisted.internet.protocol.Factory <Factory>` 
  : ``internet/protocol.py`` 
- :api:`twisted.spread.pb.PBServerFactory <PBServerFactory>` 
  : ``spread/pb.py`` 
- :api:`twisted.spread.pb.Broker <Broker>` 
  : ``spread/pb.py`` 





Other classes that are involved at some point:







- :api:`twisted.spread.pb.RemoteReference <RemoteReference>` 
  : ``spread/pb.py`` 
- :api:`twisted.spread.pb.Root <pb.Root>` 
  : ``spread/pb.py`` , actually defined as
  ``twisted.spread.flavors.Root`` 
  in ``spread/flavors.py`` 
- :api:`twisted.spread.pb.Referenceable <pb.Referenceable>` 
  : ``spread/pb.py`` , actually defined as
  ``twisted.spread.flavors.Referenceable`` 
  in ``spread/flavors.py`` 





Classes and interfaces that get involved when you start to care
about authorization and security:






- :api:`twisted.cred.portal.Portal <Portal>` 
  : ``cred/portal.py`` 
- :api:`twisted.cred.portal.IRealm <IRealm>` 
  : ``cred/portal.py`` 
- :api:`twisted.spread.pb.IPerspective <IPerspective>` 
  : ``spread/pb.py`` , which you will usually be interacting
  with via :api:`twisted.spread.pb.Avatar <pb.Avatar>` (a basic implementor of the interface).






Subclassing and Implementing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~



Technically you can subclass anything you want, but technically you
could also write a whole new framework, which would just waste a lot
of time. Knowing which classes are useful to subclass or which
interfaces to implement is one of the bits of knowledge that's crucial
to using PB (and all of Twisted) successfully. Here are some hints to
get started:







- :api:`twisted.spread.pb.Root <pb.Root>` , :api:`twisted.spread.pb.Referenceable <pb.Referenceable>` : you'll
  subclass these to make remotely-referenceable objects (i.e., objects
  which you can call methods on remotely) using PB. You don't need to
  change any of the existing behavior, just inherit all of it and add
  the remotely-accessible methods that you want to export.
- :api:`twisted.spread.pb.Avatar <pb.Avatar>` : You'll
  be subclassing this when you get into PB programming with
  authorization. This is an implementor of IPerspective.
- :api:`twisted.cred.checkers.ICredentialsChecker <ICredentialsChecker>` : Implement this if
  you want to authenticate your users against some sort of data store:
  i.e., an LDAP database, an RDBMS, etc. There are already a few
  implementations of this for various back-ends in
  twisted.cred.checkers.






..  <p>XXX: add lists of useful-to-override methods here</p> 



Things you can Call Remotely
----------------------------



At this writing, there are three "flavors" of objects that can
be accessed remotely through :api:`twisted.spread.pb.RemoteReference <RemoteReference>` objects. Each of these
flavors has a rule for how the ``callRemote`` 
message is transformed into a local method call on the server.  In
order to use one of these "flavors" , subclass them and name your
published methods with the appropriate prefix.



- :api:`twisted.spread.pb.IPerspective <twisted.spread.pb.IPerspective>` implementors
  
  
  This is the first interface we deal with. It is a "perspective" 
  onto your PB application.  Perspectives are slightly special because
  they are usually the first object that a given user can access in
  your application (after they log on).  A user should only receive a
  reference to their *own* perspective. PB works hard to
  verify, as best it can, that any method that can be called on a
  perspective directly is being called on behalf of the user who is
  represented by that perspective.  (Services with unusual
  requirements for "on behalf of" , such as simulations with the
  ability to posses another player's avatar, are accomplished by
  providing indirected access to another user's perspective.)
  
  
  
  
  
  
  Perspectives are not usually serialized as remote references, so
  do not return an IPerspective-implementor directly. 
  
  
  
  
  The way most people will want to implement IPerspective is by
  subclassing pb.Avatar. Remotely accessible methods on pb.Avatar
  instances are named with the ``perspective_`` prefix. 
  
  
  
- :api:`twisted.spread.pb.Referenceable <twisted.spread.pb.Referenceable>` 
  
  
  Referenceable objects are the simplest kind of PB object.  You can call
  methods on them and return them from methods to provide access to other
  objects' methods.  
  
  
  
  
  However, when a method is called on a Referenceable, it's not possible to
  tell who called it.
  
  
  
  
  Remotely accessible methods on Referenceables are named with the
  ``remote_`` prefix.
  
  
  
- :api:`twisted.spread.pb.Viewable <twisted.spread.pb.Viewable>` 
  
  
  Viewable objects are remotely referenceable objects which have the
  additional requirement that it must be possible to tell who is calling them.
  The argument list to a Viewable's remote methods is modified in order to
  include the Perspective representing the calling user.
  
  
  
  
  Remotely accessible methods on Viewables are named with the
  ``view_`` prefix.
  
  
  









Things you can Copy Remotely
----------------------------



In addition to returning objects that you can call remote methods on, you
can return structured copies of local objects.




There are 2 basic flavors that allow for copying objects remotely.  Again,
you can use these by subclassing them.  In order to specify what state you want
to have copied when these are serialized, you can either use the Python default 
``__getstate__`` or specialized method calls for that
flavor.







- :api:`twisted.spread.pb.Copyable <twisted.spread.pb.Copyable>` 
  
  
  This is the simpler kind of object that can be copied.  Every time this
  object is returned from a method or passed as an argument, it is serialized
  and unserialized.
  
  
  
  
  :api:`twisted.spread.pb.Copyable <Copyable>` 
  provides a method you can override, ``getStateToCopyFor(perspective)`` , which
  allows you to decide what an object will look like for the
  perspective who is requesting it. The ``perspective`` argument will be the perspective
  which is either passing an argument or returning a result an
  instance of your Copyable class. 
  
  
  
  
  For security reasons, in order to allow a particular Copyable class to
  actually be copied, you must declare a ``RemoteCopy`` 
  handler for
  that Copyable subclass.  The easiest way to do this is to declare both in the
  same module, like so:
  
  
  
  .. code-block:: python
  
  
      from twisted.spread import flavors
      class Foo(flavors.Copyable):
          pass
      class RemoteFoo(flavors.RemoteCopy):
          pass
      flavors.setUnjellyableForClass(Foo, RemoteFoo)
  
  
  
  In this case, each time a Foo is copied between peers, a RemoteFoo will be
  instantiated and populated with the Foo's state.  If you do not do this, PB
  will complain that there have been security violations, and it may close the
  connection.
  
  
  
  
- :api:`twisted.spread.pb.Cacheable <twisted.spread.pb.Cacheable>` 
  
  
  Let me preface this with a warning: Cacheable may be hard to understand.
  The motivation for it may be unclear if you don't have some experience with
  real-world applications that use remote method calling of some kind.  Once
  you understand why you need it, what it does will likely seem simple and
  obvious, but if you get confused by this, forget about it and come back
  later.  It's possible to use PB without understanding Cacheable at all.
  
  
  
  
  
  Cacheable is a flavor which is designed to be copied only when necessary,
  and updated on the fly as changes are made to it.  When passed as an argument
  or a return value, if a Cacheable exists on the side of the connection it is
  being copied to, it will be referred to by ID and not copied.
  
  
  
  
  Cacheable is designed to minimize errors involved in replicating an object
  between multiple servers, especially those related to having stale
  information.  In order to do this, Cacheable automatically registers
  observers and queries state atomically, together.  You can override the
  method ``getStateToCacheAndObserveFor(self, perspective, observer)`` in order to specify how your observers will be
  stored and updated.
  
  
  
  
  
  Similar to
  ``getStateToCopyFor`` ,
  ``getStateToCacheAndObserveFor`` gets passed a
  perspective.  It also gets passed an
  ``observer`` , which is a remote reference to a
  "secret" fourth referenceable flavor:
  :api:`twisted.spread.pb.RemoteCache <RemoteCache>` .
  
  
  
  
  A :api:`twisted.spread.pb.RemoteCache <RemoteCache>` is simply
  the object that represents your
  :api:`twisted.spread.pb.Cacheable <Cacheable>` on the other side
  of the connection.  It is registered using the same method as
  :api:`twisted.spread.pb.RemoteCopy <RemoteCopy>` , above.
  RemoteCache is different, however, in that it will be referenced by its peer.
  It acts as a Referenceable, where all methods prefixed with
  ``observe_`` will be callable remotely.  It is
  recommended that your object maintain a list (note: library support for this
  is forthcoming!) of observers, and update them using
  ``callRemote`` when the Cacheable changes in a way
  that should be noticeable to its clients.  
  
  
  
  
  Finally, when all references to a
  :api:`twisted.spread.pb.Cacheable <Cacheable>` from a given
  perspective are lost,
  ``stoppedObserving(perspective, observer)`` 
  will be called on the
  :api:`twisted.spread.pb.Cacheable <Cacheable>` , with the same
  perspective/observer pair that ``getStateToCacheAndObserveFor`` was
  originally called with.  Any cleanup remote calls can be made there, as well
  as removing the observer object from any lists which it was previously in.
  Any further calls to this observer object will be invalid.
  
  








.. rubric:: Footnotes

.. [#] Most of Twisted is like this.  Hell, most of
       Unix is like this: if *you*  think it would be useful, someone else has
       probably thought that way in the past, and acted on it, and you can take
       advantage of the tool they created to solve the same problem you're facing
       now.
