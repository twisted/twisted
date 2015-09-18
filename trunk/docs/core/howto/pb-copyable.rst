
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

PB Copyable: Passing Complex Types
==================================







Overview
--------



This chapter focuses on how to use PB to pass complex types (specifically
class instances) to and from a remote process. The first section is on
simply copying the contents of an object to a remote process (:api:`twisted.spread.pb.Copyable <pb.Copyable>` ). The second covers how
to copy those contents once, then update them later when they change (:api:`twisted.spread.pb.Cacheable <Cacheable>` ).





Motivation
----------



From the :doc:`previous chapter <pb-usage>` , you've seen how to
pass basic types to a remote process, by using them in the arguments or
return values of a :api:`twisted.spread.pb.RemoteReference.callRemote <callRemote>` function. However,
if you've experimented with it, you may have discovered problems when trying
to pass anything more complicated than a primitive int/list/dict/string
type, or another :api:`twisted.spread.pb.Referenceable <pb.Referenceable>` object. At some point you want
to pass entire objects between processes, instead of having to reduce them
down to dictionaries on one end and then re-instantiating them on the
other.





Passing Objects
---------------



The most obvious and straightforward way to send an object to a remote
process is with something like the following code. It also happens that this
code doesn't work, as will be explained below.





.. code-block:: python

    
    class LilyPond:
      def __init__(self, frogs):
        self.frogs = frogs
    
    pond = LilyPond(12)
    ref.callRemote("sendPond", pond)




If you try to run this, you might hope that a suitable remote end which
implements the ``remote_sendPond`` method would see that method get
invoked with an instance from the ``LilyPond`` class. But instead,
you'll encounter the dreaded :api:`twisted.spread.jelly.InsecureJelly <InsecureJelly>` exception. This is
Twisted's way of telling you that you've violated a security restriction,
and that the receiving end refuses to accept your object.





Security Options
~~~~~~~~~~~~~~~~



What's the big deal? What's wrong with just copying a class into another
process' namespace?




Reversing the question might make it easier to see the issue: what is the
problem with accepting a stranger's request to create an arbitrary object in
your local namespace? The real question is how much power you are granting
them: what actions can they convince you to take on the basis of the bytes
they are sending you over that remote connection.




Objects generally represent more power than basic types like strings and
dictionaries because they also contain (or reference) code, which can modify
other data structures when executed. Once previously-trusted data is
subverted, the rest of the program is compromised.




The built-in Python "batteries included" classes are relatively
tame, but you still wouldn't want to let a foreign program use them to
create arbitrary objects in your namespace or on your computer. Imagine a
protocol that involved sending a file-like object with a ``read()`` 
method that was supposed to used later to retrieve a document. Then imagine
what if that object were created with 
``os.fdopen("~/.gnupg/secring.gpg")`` . Or an instance of 
``telnetlib.Telnet("localhost", "chargen")`` . 




Classes you've written for your own program are likely to have far more
power. They may run code during ``__init__`` , or even have special
meaning simply because of their existence. A program might have 
``User`` objects to represent user accounts, and have a rule that
says all ``User`` objects in the system are referenced when
authorizing a login session. (In this system, ``User.__init__`` 
would probably add the object to a global list of known users). The simple
act of creating an object would give access to somebody. If you could be
tricked into creating a bad object, an unauthorized user would get
access.




So object creation needs to be part of a system's security design. The
dotted line between "trusted inside" and "untrusted outside" needs
to describe what may be done in response to outside events. One of those
events is the receipt of an object through a PB remote procedure call, which
is a request to create an object in your "inside" namespace. The
question is what to do in response to it. For this reason, you must
explicitly specify what remote classes will be accepted, and how their
local representatives are to be created.





What class to use?
~~~~~~~~~~~~~~~~~~



Another basic question to answer before we can do anything useful with an
incoming serialized object is: what class should we create? The simplistic
answer is to create the "same kind" that was serialized on the sender's
end of the wire, but this is not as easy or as straightforward as you might
think. Remember that the request is coming from a different program, using a
potentially different set of class libraries. In fact, since PB has also
been implemented in Java, Emacs-Lisp, and other languages, there's no
guarantee that the sender is even running Python! All we know on the
receiving end is a list of two things which describe the instance they are
trying to send us: the name of the class, and a representation of the
contents of the object.





PB lets you specify the mapping from remote class names to local classes
with the :api:`twisted.spread.jelly.setUnjellyableForClass <setUnjellyableForClass>` function  [#]_ .


This function takes a remote/sender class reference (either the
fully-qualified name as used by the sending end, or a class object from
which the name can be extracted), and a local/recipient class (used to
create the local representation for incoming serialized objects). Whenever
the remote end sends an object, the class name that they transmit is looked
up in the table controlled by this function. If a matching class is found,
it is used to create the local object. If not, you get the 
``InsecureJelly`` exception.




In general you expect both ends to share the same codebase: either you
control the program that is running on both ends of the wire, or both
programs share some kind of common language that is implemented in code
which exists on both ends. You wouldn't expect them to send you an object of
the MyFooziWhatZit class unless you also had a definition for that class. So
it is reasonable for the Jelly layer to reject all incoming classes except
the ones that you have explicitly marked with 
``setUnjellyableForClass`` . But keep in mind that the sender's idea
of a ``User`` object might differ from the recipient's, either
through namespace collisions between unrelated packages, version skew
between nodes that haven't been updated at the same rate, or a malicious
intruder trying to cause your code to fail in some interesting or
potentially vulnerable way.






pb.Copyable
-----------



Ok, enough of this theory. How do you send a fully-fledged object from
one side to the other?





:download:`copy_sender.py <listings/pb/copy_sender.py>`

.. literalinclude:: listings/pb/copy_sender.py



:download:`copy_receiver.tac <listings/pb/copy_receiver.tac>`

.. literalinclude:: listings/pb/copy_receiver.tac


The sending side has a class called ``LilyPond`` . To make this
eligible for transport through ``callRemote`` (either as an
argument, a return value, or something referenced by either of those [like a
dictionary value]), it must inherit from one of the four :api:`twisted.spread.pb.Serializable <Serializable>` classes. In this section,
we focus on :api:`twisted.spread.pb.Copyable <Copyable>` .
The copyable subclass of ``LilyPond`` is called 
``CopyPond`` . We create an instance of it and send it through 
``callRemote`` as an argument to the receiver's 
``remote_takePond`` method. The Jelly layer will serialize
("jelly" ) that object as an instance with a class name of"copy_sender.CopyPond" and some chunk of data that represents the
object's state. ``pond.__class__.__module__`` and 
``pond.__class__.__name__`` are used to derive the class name
string. The object's :api:`twisted.spread.flavors.Copyable.getStateToCopy <getStateToCopy>` method is
used to get the state: this is provided by :api:`twisted.spread.pb.Copyable <pb.Copyable>` , and the default just retrieves 
``self.__dict__`` . This works just like the optional 
``__getstate__`` method used by ``pickle`` . The pair of
name and state are sent over the wire to the receiver.




The receiving end defines a local class named ``ReceiverPond`` 
to represent incoming ``LilyPond`` instances. This class derives
from the sender's ``LilyPond`` class (with a fully-qualified name
of ``copy_sender.LilyPond`` ), which specifies how we expect it to
behave. We trust that this is the same ``LilyPond`` class as the
sender used. (At the very least, we hope ours will be able to accept a state
created by theirs). It also inherits from :api:`twisted.spread.pb.RemoteCopy <pb.RemoteCopy>` , which is a requirement for all
classes that act in this local-representative role (those which are given to
the second argument of ``setUnjellyableForClass`` ). 
``RemoteCopy`` provides the methods that tell the Jelly layer how
to create the local object from the incoming serialized state.




Then ``setUnjellyableForClass`` is used to register the two
classes. This has two effects: instances of the remote class (the first
argument) will be allowed in through the security layer, and instances of
the local class (the second argument) will be used to contain the state that
is transmitted when the sender serializes the remote object.




When the receiver unserializes ("unjellies" ) the object, it will
create an instance of the local ``ReceiverPond`` class, and hand
the transmitted state (usually in the form of a dictionary) to that object's 
:api:`twisted.spread.flavors.RemoteCopy.setCopyableState <setCopyableState>` method.
This acts just like the ``__setstate__`` method that 
``pickle`` uses when unserializing an object. 
``getStateToCopy`` /``setCopyableState`` are distinct from 
``__getstate__`` /``__setstate__`` to allow objects to be
persisted (across time) differently than they are transmitted (across
[memory]space).




When this is run, it produces the following output:





.. code-block:: console

    
    [-] twisted.spread.pb.PBServerFactory starting on 8800
    [-] Starting factory <twisted.spread.pb.PBServerFactory instance at
    0x406159cc>
    [Broker,0,127.0.0.1]  got pond: <__builtin__.ReceiverPond instance at
    0x406ec5ec>
    [Broker,0,127.0.0.1] 7 frogs





.. code-block:: console

    
    $ ./copy_sender.py
    7 frogs
    copy_sender.CopyPond
    pond arrived safe and sound
    Main loop terminated.
    $







Controlling the Copied State
~~~~~~~~~~~~~~~~~~~~~~~~~~~~



By overriding ``getStateToCopy`` and 
``setCopyableState`` , you can control how the object is transmitted
over the wire. For example, you might want perform some data-reduction:
pre-compute some results instead of sending all the raw data over the wire.
Or you could replace references to a local object on the sender's side with
markers before sending, then upon receipt replace those markers with
references to a receiver-side proxy that could perform the same operations
against a local cache of data.




Another good use for ``getStateToCopy`` is to implement "local-only" attributes: data that is only accessible by the local
process, not to any remote users. For example, a ``.password`` 
attribute could be removed from the object state before sending to a remote
system. Combined with the fact that ``Copyable`` objects return
unchanged from a round trip, this could be used to build a
challenge-response system (in fact PB does this with 
``pb.Referenceable`` objects to implement authorization as
described :doc:`here <pb-cred>` ).




Whatever ``getStateToCopy`` returns from the sending object will
be serialized and sent over the wire; ``setCopyableState`` gets
whatever comes over the wire and is responsible for setting up the state of
the object it lives in.






:download:`copy2_classes.py <listings/pb/copy2_classes.py>`

.. literalinclude:: listings/pb/copy2_classes.py



:download:`copy2_sender.py <listings/pb/copy2_sender.py>`

.. literalinclude:: listings/pb/copy2_sender.py



:download:`copy2_receiver.py <listings/pb/copy2_receiver.py>`

.. literalinclude:: listings/pb/copy2_receiver.py


In this example, the classes are defined in a separate source file, which
also sets up the binding between them. The ``SenderPond`` and ``ReceiverPond`` are unrelated save for this binding: they happen
to implement the same methods, but use different internal instance variables
to accomplish them.




The recipient of the object doesn't even have to import the class
definition into their namespace. It is sufficient that they import the class
definition (and thus execute the ``setUnjellyableForClass`` 
statement). The Jelly layer remembers the class definition until a matching
object is received. The sender of the object needs the definition, of
course, to create the object in the first place.




When run, the ``copy2`` example emits the following:





.. code-block:: console

    
    $ twistd -n -y copy2_receiver.py
    [-] twisted.spread.pb.PBServerFactory starting on 8800
    [-] Starting factory <twisted.spread.pb.PBServerFactory instance at
    0x40604b4c>
    [Broker,0,127.0.0.1]  got pond: <copy2_classes.ReceiverPond instance at
    0x406eb2ac>
    [Broker,0,127.0.0.1]  count 7





.. code-block:: console

    
    $ ./copy2_sender.py
    count 7
    pond arrived safe and sound
    Main loop terminated.







Things To Watch Out For
~~~~~~~~~~~~~~~~~~~~~~~






- The first argument to ``setUnjellyableForClass`` must refer
  to the class *as known by the sender* . The sender has no way of
  knowing about how your local ``import`` statements are set up,
  and Python's flexible namespace semantics allow you to access the same
  class through a variety of different names. You must match whatever the
  sender does. Having both ends import the class from a separate file, using
  a canonical module name (no "sibling imports" ), is a good way to get
  this right, especially when both the sending and the receiving classes are
  defined together, with the ``setUnjellyableForClass`` immediately
  following them.
- The class that is sent must inherit from :api:`twisted.spread.pb.Copyable <pb.Copyable>` . The class that is registered to
  receive it must inherit from :api:`twisted.spread.pb.RemoteCopy <pb.RemoteCopy>`  [#]_ . 
- The same class can be used to send and receive. Just have it inherit
  from both ``pb.Copyable`` and ``pb.RemoteCopy`` . This
  will also make it possible to send the same class symmetrically back and
  forth over the wire. But don't get confused about when it is coming (and
  using ``setCopyableState`` ) versus when it is going (using
  ``getStateToCopy`` ).
- :api:`twisted.spread.jelly.InsecureJelly <InsecureJelly>` 
  exceptions are raised by the receiving end. They will be delivered
  asynchronously to an ``errback`` handler. If you do not add one
  to the ``Deferred`` returned by ``callRemote`` , then you
  will never receive notification of the problem. 
- The class that is derived from :api:`twisted.spread.pb.RemoteCopy <pb.RemoteCopy>` will be created using a
  constructor ``__init__`` method that takes no arguments. All
  setup must be performed in the ``setCopyableState`` method. As
  the docstring on :api:`twisted.spread.pb.RemoteCopy <RemoteCopy>` says, don't implement a
  constructor that requires arguments in a subclass of
  ``RemoteCopy`` .


..    XXX: check this, the code around jelly._Unjellier.unjelly:489 tries to avoid 



..    calling <code>__init__</code> just in case the constructor requires 



..    args. 







More Information
~~~~~~~~~~~~~~~~






- ``pb.Copyable`` is mostly implemented
  in ``twisted.spread.flavors`` , and the docstrings there are
  the best source of additional information.
- ``Copyable`` is also used in :api:`twisted.web.distrib <twisted.web.distrib>` to deliver HTTP requests to other
  programs for rendering, allowing subtrees of URL space to be delegated to
  multiple programs (on multiple machines).
- :api:`twisted.manhole.explorer <twisted.manhole.explorer>` also uses
  ``Copyable`` to distribute debugging information from the program
  under test to the debugging tool.







pb.Cacheable
------------



Sometimes the object you want to send to the remote process is big and
slow. "big" means it takes a lot of data (storage, network bandwidth,
processing) to represent its state. "slow" means that state doesn't
change very frequently. It may be more efficient to send the full state only
once, the first time it is needed, then afterwards only send the differences
or changes in state whenever it is modified. The :api:`twisted.spread.pb.Cacheable <pb.Cacheable>` class provides a framework to
implement this.




:api:`twisted.spread.pb.Cacheable <pb.Cacheable>` is derived
from :api:`twisted.spread.pb.Copyable <pb.Copyable>` , so it is
based upon the idea of an object's state being captured on the sending side,
and then turned into a new object on the receiving side. This is extended to
have an object "publishing" on the sending side (derived from :api:`twisted.spread.pb.Cacheable <pb.Cacheable>` ), matched with one"observing" on the receiving side (derived from :api:`twisted.spread.pb.RemoteCache <pb.RemoteCache>` ).




To effectively use ``pb.Cacheable`` , you need to isolate changes
to your object into accessor functions (specifically "setter" 
functions). Your object needs to get control *every* single time some
attribute is changed [#]_ .




You derive your sender-side class from ``pb.Cacheable`` , and you
add two methods: :api:`twisted.spread.flavors.Cacheable.getStateToCacheAndObserveFor <getStateToCacheAndObserveFor>` 
and :api:`twisted.spread.flavors.Cacheable.stoppedObserving <stoppedObserving>` . The first
is called when a remote caching reference is first created, and retrieves
the data with which the cache is first filled. It also provides an
object called the "observer"  [#]_ that points at that receiver-side cache. Every time the state of the object
is changed, you give a message to the observer, informing them of the
change. The other method, ``stoppedObserving`` , is called when the
remote cache goes away, so that you can stop sending updates.




On the receiver end, you make your cache class inherit from :api:`twisted.spread.pb.RemoteCache <pb.RemoteCache>` , and implement the 
``setCopyableState`` as you would for a ``pb.RemoteCopy`` 
object. In addition, you must implement methods to receive the updates sent
to the observer by the ``pb.Cacheable`` : these methods should have
names that start with ``observe_`` , and match the 
``callRemote`` invocations from the sender side just as the usual 
``remote_*`` and ``perspective_*`` methods match normal 
``callRemote`` calls. 




The first time a reference to the ``pb.Cacheable`` object is
sent to any particular recipient, a sender-side Observer will be created for
it, and the ``getStateToCacheAndObserveFor`` method will be called
to get the current state and register the Observer. The state which that
returns is sent to the remote end and turned into a local representation
using ``setCopyableState`` just like ``pb.RemoteCopy`` ,
described above (in fact it inherits from that class). 




After that, your "setter" functions on the sender side should call 
``callRemote`` on the Observer, which causes ``observe_*`` 
methods to run on the receiver, which are then supposed to update the
receiver-local (cached) state.




When the receiver stops following the cached object and the last
reference goes away, the ``pb.RemoteCache`` object can be freed.
Just before it dies, it tells the sender side it no longer cares about the
original object. When *that* reference count goes to zero, the
Observer goes away and the ``pb.Cacheable`` object can stop
announcing every change that takes place. The :api:`twisted.spread.flavors.Cacheable.stoppedObserving <stoppedObserving>` method is
used to tell the ``pb.Cacheable`` that the Observer has gone
away.




With the ``pb.Cacheable`` and ``pb.RemoteCache`` 
classes in place, bound together by a call to 
``pb.setUnjellyableForClass`` , all that remains is to pass a
reference to your ``pb.Cacheable`` over the wire to the remote end.
The corresponding ``pb.RemoteCache`` object will automatically be
created, and the matching methods will be used to keep the receiver-side
slave object in sync with the sender-side master object.





Example
~~~~~~~



Here is a complete example, in which the ``MasterDuckPond`` is
controlled by the sending side, and the ``SlaveDuckPond`` is a
cache that tracks changes to the master:





:download:`cache_classes.py <listings/pb/cache_classes.py>`

.. literalinclude:: listings/pb/cache_classes.py



:download:`cache_sender.py <listings/pb/cache_sender.py>`

.. literalinclude:: listings/pb/cache_sender.py



:download:`cache_receiver.py <listings/pb/cache_receiver.py>`

.. literalinclude:: listings/pb/cache_receiver.py


When run, this example emits the following:





.. code-block:: console

    
    $ twistd -n -y cache_receiver.py
    [-] twisted.spread.pb.PBServerFactory starting on 8800
    [-] Starting factory <twisted.spread.pb.PBServerFactory instance at
    0x40615acc>
    [Broker,0,127.0.0.1]  cache - sitting, er, setting ducks
    [Broker,0,127.0.0.1] got pond: <cache_classes.SlaveDuckPond instance at
    0x406eb5ec>
    [Broker,0,127.0.0.1] [2] ducks:  ['one duck', 'two duck']
    [Broker,0,127.0.0.1]  cache - addDuck
    [Broker,0,127.0.0.1] [3] ducks:  ['one duck', 'two duck', 'ugly duckling']
    [Broker,0,127.0.0.1]  cache - removeDuck
    [Broker,0,127.0.0.1] [2] ducks:  ['two duck', 'ugly duckling']
    [Broker,0,127.0.0.1] dropping pond





.. code-block:: console

    
    $ ./cache_sender.py
    I have [2] ducks
    I have [3] ducks
    I have [2] ducks
    Main loop terminated.





Points to notice:






- There is one ``Observer`` for each remote program that holds
  an active reference. Multiple references inside the same program don't
  matter: the serialization layer notices the duplicates and does the
  appropriate reference counting [#]_ .
- Multiple Observers need to be kept in a list, and all of them need to
  be updated when something changes. By sending the initial state at the
  same time as you add the observer to the list, in a single atomic action
  that cannot be interrupted by a state change, you insure that you can send
  the same status update to all the observers.
- The ``observer.callRemote`` calls can still fail. If the
  remote side has disconnected very recently and
  ``stoppedObserving`` has not yet been called, you may get a
  ``DeadReferenceError`` . It is a good idea to add an errback to
  those ``callRemote`` s to throw away such an error. This is a
  useful idiom:
  
  
  
  .. code-block:: python
  
      observer.callRemote('foo', arg).addErrback(lambda f: None)
  
  


..    (XXX: verify that this is actually a concern) 

- ``getStateToCacheAndObserverFor`` must return some object
  that represents the current state of the object. This may simply be the
  object's ``__dict__`` attribute. It is a good idea to remove the
  ``pb.Cacheable`` -specific members of it before sending it to the
  remote end. The list of Observers, in particular, should be left out, to
  avoid dizzying recursive Cacheable references. The mind boggles as to the
  potential consequences of leaving in such an item.
- A ``perspective`` argument is available to
  ``getStateToCacheAndObserveFor`` , as well as
  ``stoppedObserving`` . I think the purpose of this is to allow
  viewer-specific changes to the way the cache is updated. If all remote
  viewers are supposed to see the same data, it can be ignored.






..  <p>XXX: understand, then explain use of varying cached state depending upon 



..  perspective.</p> 



More Information
~~~~~~~~~~~~~~~~





- The best source for information comes from the docstrings
  in :api:`twisted.spread.flavors <twisted.spread.flavors>` ,
  where ``pb.Cacheable`` is implemented.
- :api:`twisted.manhole.explorer <twisted.manhole.explorer>` uses
  ``Cacheable`` , and does some fairly interesting things with it.
- The :api:`twisted.spread.publish <spread.publish>` module also
  uses ``Cacheable`` , and might be a source of further
  information.








.. rubric:: Footnotes

.. [#] Note that, in this context, "unjelly"  is
       a verb with the opposite meaning of "jelly" . The verb "to jelly" 
       means to serialize an object or data structure into a sequence of bytes (or
       other primitive transmittable/storable representation), while "to unjelly"  means to unserialize the bytestream into a live object in the
       receiver's memory space. "Unjellyable"  is a noun, (*not*  an
       adjective), referring to the class that serves as a destination or
       recipient of the unjellying process. "A is unjellyable into B"  means
       that a serialized representation A (of some remote object) can be
       unserialized into a local object of type B. It is these objects "B" 
       that are the "Unjellyable"  second argument of the 
       ``setUnjellyableForClass``  function.
       In particular, "unjellyable"  does *not*  mean "cannot be jellied" . :api:`twisted.spread.jelly.Unpersistable <Unpersistable>`  means "not persistable" , but "unjelly" , "unserialize" , and "unpickle" 
       mean to reverse the operations of "jellying" , "serializing" , and
       "pickling" .
.. [#] :api:`twisted.spread.pb.RemoteCopy <pb.RemoteCopy>`  is actually defined
         in :api:`twisted.spread.flavors <twisted.spread.flavors>` , but
         ``pb.RemoteCopy``  is the preferred way to access it
.. [#] Of course you could be clever and
       add a hook to ``__setattr__`` , along with magical change-announcing
       subclasses of the usual builtin types, to detect changes that result from
       normal "="  set operations. The semi-magical "property attributes" 
       that were introduced in Python 2.2 could be useful too. The result might be
       hard to maintain or extend, though.
.. [#] This is actually a :api:`twisted.spread.pb.RemoteCacheObserver <RemoteCacheObserver>` , but it isn't very
       useful to subclass or modify, so simply treat it as a little demon that sits
       in your ``pb.Cacheable``  class and helps you distribute change
       notifications. The only useful thing to do with it is to run its 
       ``callRemote``  method, which acts just like a normal 
       ``pb.Referenceable`` 's method of the same name.
.. [#] This applies to
         multiple references through the same :api:`twisted.spread.pb.Broker <Broker>` . If you've managed to make multiple
         TCP connections to the same program, you deserve whatever you get.
