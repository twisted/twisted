
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Using Perspective Broker
========================







Basic Example
-------------



The first example to look at is a complete (although somewhat trivial)
application. It uses ``PBServerFactory()`` on the server side, and 
``PBClientFactory()`` on the client side.





:download:`pbsimple.py <../examples/pbsimple.py>`

.. literalinclude:: ../examples/pbsimple.py



:download:`pbsimpleclient.py <../examples/pbsimpleclient.py>`

.. literalinclude:: ../examples/pbsimpleclient.py


First we look at the server. This defines an Echoer class (derived from 
:api:`twisted.spread.pb.Root <pb.Root>` ), with a method called 
``remote_echo()`` . 
:api:`twisted.spread.pb.Root <pb.Root>` objects (because of
their inheritance of 
:api:`twisted.spread.pb.Referenceable <pb.Referenceable>` , described
later) can define methods with names of the form ``remote_*`` ; a
client which obtains a remote reference to that 
:api:`twisted.spread.pb.Root <pb.Root>` object will be able to
invoke those methods.




The :api:`twisted.spread.pb.Root <pb.Root>` -ish object is
given to a :api:`twisted.spread.pb.PBServerFactory <pb.PBServerFactory>` ``()`` . This is a 
:api:`twisted.internet.protocol.Factory <Factory>` object like
any other: the :api:`twisted.internet.protocol.Protocol <Protocol>` objects it creates for new
connections know how to speak the PB protocol. The object you give to 
``pb.PBServerFactory()`` becomes the "root object" , which
simply makes it available for the client to retrieve. The client may only
request references to the objects you want to provide it: this helps you
implement your security model. Because it is so common to export just a
single object (and because a ``remote_*`` method on that one can
return a reference to any other object you might want to give out), the
simplest example is one where the :api:`twisted.spread.pb.PBServerFactory <PBServerFactory>` is given the root object, and
the client retrieves it.




The client side uses 
:api:`twisted.spread.pb.PBClientFactory <pb.PBClientFactory>` to make a
connection to a given port. This is a two-step process involving opening
a TCP connection to a given host and port and requesting the root object
using ``.getRootObject()`` .




Because ``.getRootObject()`` has to wait until a network
connection has been made and exchange some data, it may take a while,
so it returns a Deferred, to which the gotObject() callback is
attached. (See the documentation on :doc:`Deferring Execution <defer>` for a complete explanation of :api:`twisted.internet.defer.Deferred <Deferred>` s). If and when the
connection succeeds and a reference to the remote root object is
obtained, this callback is run. The first argument passed to the
callback is a remote reference to the distant root object.  (you can
give other arguments to the callback too, see the other parameters for 
``.addCallback()`` and ``.addCallbacks()`` ).




The callback does:





.. code-block:: python

    
    object.callRemote("echo", "hello network")




which causes the server's ``.remote_echo()`` method to be invoked.
(running ``.callRemote("boom")`` would cause 
``.remote_boom()`` to be run, etc). Again because of the delay
involved, ``callRemote()`` returns a 
:api:`twisted.internet.defer.Deferred <Deferred>` . Assuming the
remote method was run without causing an exception (including an attempt to
invoke an unknown method), the callback attached to that 
:api:`twisted.internet.defer.Deferred <Deferred>` will be
invoked with any objects that were returned by the remote method call.




In this example, the server's ``Echoer`` object has a method
invoked, *exactly* as if some code on the server side had done:





.. code-block:: python

    
    echoer_object.remote_echo("hello network")




and from the definition of ``remote_echo()`` we see that this just
returns the same string it was given: "hello network" .




From the client's point of view, the remote call gets another :api:`twisted.internet.defer.Deferred <Deferred>` object instead of
that string. ``callRemote()`` *always* returns a :api:`twisted.internet.defer.Deferred <Deferred>` . This is why PB is
described as a system for "translucent" remote method calls instead of "transparent" ones: you cannot pretend that the remote object is really
local. Trying to do so (as some other RPC mechanisms do, coughCORBAcough)
breaks down when faced with the asynchronous nature of the network. Using
Deferreds turns out to be a very clean way to deal with the whole thing.




The remote reference object (the one given to 
``getRootObject()`` 's success callback) is an instance the :api:`twisted.spread.pb.RemoteReference <RemoteReference>` class. This means
you can use it to invoke methods on the remote object that it refers to. Only
instances of :api:`twisted.spread.pb.RemoteReference <RemoteReference>` are eligible for 
``.callRemote()`` . The :api:`twisted.spread.pb.RemoteReference <RemoteReference>` object is the one that lives
on the remote side (the client, in this case), not the local side (where the
actual object is defined).




In our example, the local object is that ``Echoer()`` instance,
which inherits from :api:`twisted.spread.pb.Root <pb.Root>` ,
which inherits from 
:api:`twisted.spread.pb.Referenceable <pb.Referenceable>` . It is that 
``Referenceable`` class that makes the object eligible to be available
for remote method calls [#]_ . If you have
an object that is Referenceable, then any client that manages to get a
reference to it can invoke any ``remote_*`` methods they please.



.. note::
   
   
   The *only* thing they can do is invoke those
   methods.  In particular, they cannot access attributes. From a security point
   of view, you control what they can do by limiting what the ``remote_*`` methods can do.
   
   
   
   
   Also note: the other classes like 
   :api:`twisted.spread.pb.Referenceable <Referenceable>` allow access to
   other methods, in particular ``perspective_*`` and ``view_*`` 
   may be accessed.  Don't write local-only methods with these names, because then
   remote callers will be able to do more than you intended.
   
   
   
   
   Also also note: the other classes like 
   :api:`twisted.spread.pb.Copyable <pb.Copyable>` *do* allow
   access to attributes, but you control which ones they can see.
   
   




You don't have to be a 
:api:`twisted.spread.pb.Root <pb.Root>` to be remotely callable,
but you do have to be 
:api:`twisted.spread.pb.Referenceable <pb.Referenceable>` .  (Objects that
inherit from :api:`twisted.spread.pb.Referenceable <pb.Referenceable>` 
but not from :api:`twisted.spread.pb.Root <pb.Root>` can be
remotely called, but only 
:api:`twisted.spread.pb.Root <pb.Root>` -ish objects can be given
to the :api:`twisted.spread.pb.PBServerFactory <PBServerFactory>` .)





Complete Example
----------------



Here is an example client and server which uses :api:`twisted.spread.pb.Referenceable <pb.Referenceable>` as a root object and as the
result of a remotely exposed method.  In each context, methods can be invoked
on the exposed :api:`twisted.spread.pb.Referenceable <Referenceable>` 
instance.  In this example, the initial root object has a method that returns a
reference to the second object.





:download:`pb1server.py <listings/pb/pb1server.py>`

.. literalinclude:: listings/pb/pb1server.py



:download:`pb1client.py <listings/pb/pb1client.py>`

.. literalinclude:: listings/pb/pb1client.py


:api:`twisted.spread.pb.PBClientFactory.getRootObject <pb.PBClientFactory.getRootObject>` will
handle all the details of waiting for the creation of a connection.
It returns a :api:`twisted.internet.defer.Deferred <Deferred>` , which will have its
callback called when the reactor connects to the remote server and 
:api:`twisted.spread.pb.PBClientFactory <pb.PBClientFactory>` gets the
root, and have its ``errback`` called when the
object-connection fails for any reason, whether it was host lookup
failure, connection refusal, or some server-side error.




The root object has a method called ``remote_getTwo`` , which
returns the ``Two()`` instance. On the client end, the callback gets
a :api:`twisted.spread.pb.RemoteReference <RemoteReference>` to that
instance. The client can then invoke two's ``.remote_three()`` 
method.




:api:`twisted.spread.pb.RemoteReference <RemoteReference>` 
objects have one method which is their purpose for being: ``callRemote`` .  This method allows you to call a
remote method on the object being referred to by the Reference.  :api:`twisted.spread.pb.RemoteReference.callRemote <RemoteReference.callRemote>` , like :api:`twisted.spread.pb.PBClientFactory.getRootObject <pb.PBClientFactory.getRootObject>` , returns
a :api:`twisted.internet.defer.Deferred <Deferred>` .
When a response to the method-call being sent arrives, the :api:`twisted.internet.defer.Deferred <Deferred>` 's ``callback`` or ``errback`` 
will be made, depending on whether an error occurred in processing the
method call.




You can use this technique to provide access to arbitrary sets of objects.
Just remember that any object that might get passed "over the wire" must
inherit from :api:`twisted.spread.pb.Referenceable <Referenceable>` 
(or one of the other flavors). If you try to pass a non-Referenceable object
(say, by returning one from a ``remote_*`` method), you'll get an 
:api:`twisted.spread.jelly.InsecureJelly <InsecureJelly>` 
exception [#]_ .






References can come back to you
-------------------------------



If your server gives a reference to a client, and then that client gives
the reference back to the server, the server will wind up with the same
object it gave out originally. The serialization layer watches for returning
reference identifiers and turns them into actual objects. You need to stay
aware of where the object lives: if it is on your side, you do actual method
calls. If it is on the other side, you do 
``.callRemote()``  [#]_ .





:download:`pb2server.py <listings/pb/pb2server.py>`

.. literalinclude:: listings/pb/pb2server.py



:download:`pb2client.py <listings/pb/pb2client.py>`

.. literalinclude:: listings/pb/pb2client.py


The server gives a ``Two()`` instance to the client, who then
returns the reference back to the server. The server compares the "two" 
given with the "two" received and shows that they are the same, and that
both are real objects instead of remote references.




A few other techniques are demonstrated in ``pb2client.py`` . One
is that the callbacks are added with ``.addCallback`` instead
of ``.addCallbacks`` . As you can tell from the :doc:`Deferred <defer>` documentation, ``.addCallback`` is a
simplified form which only adds a success callback. The other is that to
keep track of state from one callback to the next (the remote reference to
the main One() object), we create a simple class, store the reference in an
instance thereof, and point the callbacks at a sequence of bound methods.
This is a convenient way to encapsulate a state machine. Each response kicks
off the next method, and any data that needs to be carried from one state to
the next can simply be saved as an attribute of the object.




Remember that the client can give you back any remote reference you've
given them. Don't base your zillion-dollar stock-trading clearinghouse
server on the idea that you trust the client to give you back the right
reference. The security model inherent in PB means that they can *only* 
give you back a reference that you've given them for the current connection
(not one you've given to someone else instead, nor one you gave them last
time before the TCP session went down, nor one you haven't yet given to the
client), but just like with URLs and HTTP cookies, the particular reference
they give you is entirely under their control.






References to client-side objects
---------------------------------



Anything that's Referenceable can get passed across the wire, *in either direction* . The "client" can give a reference to the
"server" , and then the server can use .callRemote() to invoke methods on
the client end. This fuzzes the distinction between "client" and
"server" : the only real difference is who initiates the original TCP
connection; after that it's all symmetric.





:download:`pb3server.py <listings/pb/pb3server.py>`

.. literalinclude:: listings/pb/pb3server.py



:download:`pb3client.py <listings/pb/pb3client.py>`

.. literalinclude:: listings/pb/pb3client.py


In this example, the client gives a reference to its own object to the
server. The server then invokes a remote method on the client-side
object.






Raising Remote Exceptions
-------------------------



Everything so far has covered what happens when things go right. What
about when they go wrong? The Python Way is to raise an exception of some
sort. The Twisted Way is the same.




The only special thing you do is to define your ``Exception`` 
subclass by deriving it from :api:`twisted.spread.pb.Error <pb.Error>` . When any remotely-invokable method
(like ``remote_*`` or ``perspective_*`` ) raises a 
``pb.Error`` -derived exception, a serialized form of that Exception
object will be sent back over the wire [#]_ . The other side (which
did ``callRemote`` ) will have the "``errback``" 
callback run with a :api:`twisted.python.failure.Failure <Failure>` object that contains a copy of
the exception object. This ``Failure`` object can be queried to
retrieve the error message and a stack traceback.




:api:`twisted.python.failure.Failure <Failure>` is a
special class, defined in ``twisted/python/failure.py`` , created to
make it easier to handle asynchronous exceptions. Just as exception handlers
can be nested, ``errback`` functions can be chained. If one errback
can't handle the particular type of failure, it can be "passed along" to a
errback handler further down the chain.




For simple purposes, think of the ``Failure`` as just a container
for remotely-thrown ``Exception`` objects. To extract the string that
was put into the exception, use its ``.getErrorMessage()`` method.
To get the type of the exception (as a string), look at its 
``.type`` attribute. The stack traceback is available too. The
intent is to let the errback function get just as much information about the
exception as Python's normal ``try:`` clauses do, even though the
exception occurred in somebody else's memory space at some unknown time in
the past.





:download:`exc_server.py <listings/pb/exc_server.py>`

.. literalinclude:: listings/pb/exc_server.py



:download:`exc_client.py <listings/pb/exc_client.py>`

.. literalinclude:: listings/pb/exc_client.py



.. code-block:: console

    
    $ ./exc_client.py 
    got remote Exception
     .__class__ = twisted.spread.pb.CopiedFailure
     .getErrorMessage() = fall down go boom
     .type = __main__.MyError
    Main loop terminated.




Oh, and what happens if you raise some other kind of exception? Something
that *isn't* subclassed from ``pb.Error`` ? Well, those are
called "unexpected exceptions" , which make Twisted think that something
has *really* gone wrong. These will raise an exception on the 
*server* side. This won't break the connection (the exception is
trapped, just like most exceptions that occur in response to network
traffic), but it will print out an unsightly stack trace on the server's
stderr with a message that says "Peer Will Receive PB Traceback" , just
as if the exception had happened outside a remotely-invokable method. (This
message will go the current log target, if :api:`twisted.python.log.startLogging <log.startLogging>` was used to redirect it). The
client will get the same ``Failure`` object in either case, but
subclassing your exception from ``pb.Error`` is the way to tell
Twisted that you expect this sort of exception, and that it is ok to just
let the client handle it instead of also asking the server to complain. Look
at ``exc_client.py`` and change it to invoke ``broken2()`` 
instead of ``broken()`` to see the change in the server's
behavior.




If you don't add an ``errback`` function to the :api:`twisted.internet.defer.Deferred <Deferred>` , then a remote
exception will still send a ``Failure`` object back over, but it
will get lodged in the ``Deferred`` with nowhere to go. When that 
``Deferred`` finally goes out of scope, the side that did 
``callRemote`` will emit a message about an "Unhandled error in Deferred" , along with an ugly stack trace. It can't raise an exception at
that point (after all, the ``callRemote`` that triggered the
problem is long gone), but it will emit a traceback. So be a good programmer
and *always* add ``errback`` handlers, even if they are just
calls to :api:`twisted.python.log.err <log.err>` .





Try/Except blocks and :api:`twisted.python.failure.Failure.trap <Failure.trap>`
-------------------------------------------------------------------------------



To implement the equivalent of the Python try/except blocks (which can
trap particular kinds of exceptions and pass others "up" to
higher-level ``try/except`` blocks), you can use the 
``.trap()`` method in conjunction with multiple 
``errback`` handlers on the ``Deferred`` . Re-raising an
exception in an ``errback`` handler serves to pass that new
exception to the next handler in the chain. The ``trap`` method is
given a list of exceptions to look for, and will re-raise anything that
isn't on the list. Instead of passing unhandled exceptions "up" to an
enclosing ``try`` block, this has the effect of passing the
exception "off" to later ``errback`` handlers on the same ``Deferred`` . The ``trap`` calls are used in chained
errbacks to test for each kind of exception in sequence. 





:download:`trap_server.py <listings/pb/trap_server.py>`

.. literalinclude:: listings/pb/trap_server.py



:download:`trap_client.py <listings/pb/trap_client.py>`

.. literalinclude:: listings/pb/trap_client.py



.. code-block:: console

    
    $ ./trap_client.py 
    callOne: call with safe object
     method successful, response: response
    callTwo: call with dangerous object
     InsecureJelly: you tried to send something unsafe to them
    callThree: call that raises remote exception
     remote raised a MyException
    telling them to shut down
    callFour: call on stale reference
     stale reference: the client disconnected or crashed





In this example, ``callTwo`` tries to send an instance of a
locally-defined class through ``callRemote`` . The default security
model implemented by :api:`twisted.spread.jelly <jelly>` 
on the remote end will not allow unknown classes to be unserialized (i.e.
taken off the wire as a stream of bytes and turned back into an object: a
living, breathing instance of some class): one reason is that it does not
know which local class ought to be used to create an instance that
corresponds to the remote object [#]_ .




The receiving end of the connection gets to decide what to accept and what
to reject. It indicates its disapproval by raising a :api:`twisted.spread.jelly.InsecureJelly <jelly.InsecureJelly>` exception. Because it occurs
at the remote end, the exception is returned to the caller asynchronously,
so an ``errback`` handler for the associated ``Deferred`` 
is run. That errback receives a ``Failure`` which wraps the 
``InsecureJelly`` .





Remember that ``trap`` re-raises exceptions that it wasn't asked
to look for. You can only check for one set of exceptions per errback
handler: all others must be checked in a subsequent handler. 
``check_MyException`` shows how multiple kinds of exceptions can be
checked in a single errback: give a list of exception types to 
``trap`` , and it will return the matching member. In this case, the
kinds of exceptions we are checking for (``MyException`` and 
``MyOtherException`` ) may be raised by the remote end: they inherit
from :api:`twisted.spread.pb.Error <pb.Error>` .




The handler can return ``None`` to terminate processing of the
errback chain (to be precise, it switches to the callback that follows the
errback; if there is no callback then processing terminates). It is a good
idea to put an errback that will catch everything (no ``trap`` 
tests, no possible chance of raising more exceptions, always returns 
``None`` ) at the end of the chain. Just as with regular ``try: except:`` handlers, you need to think carefully about ways in which
your errback handlers could themselves raise exceptions. The extra
importance in an asynchronous environment is that an exception that falls
off the end of the ``Deferred`` will not be signalled until that 
``Deferred`` goes out of scope, and at that point may only cause a
log message (which could even be thrown away if :api:`twisted.python.log.startLogging <log.startLogging>` is not used to point it at
stdout or a log file). In contrast, a synchronous exception that is not
handled by any other ``except:`` block will very visibly terminate
the program immediately with a noisy stack trace.




``callFour`` shows another kind of exception that can occur
while using ``callRemote`` : :api:`twisted.spread.pb.DeadReferenceError <pb.DeadReferenceError>` . This one occurs when the
remote end has disconnected or crashed, leaving the local side with a stale
reference. This kind of exception happens to be reported right away (XXX: is
this guaranteed? probably not), so must be caught in a traditional
synchronous ``try: except pb.DeadReferenceError`` block. 




Yet another kind that can occur is a :api:`twisted.spread.pb.PBConnectionLost <pb.PBConnectionLost>` exception. This occurs
(asynchronously) if the connection was lost while you were waiting for a ``callRemote`` call to complete. When the line goes dead, all
pending requests are terminated with this exception. Note that you have no
way of knowing whether the request made it to the other end or not, nor how
far along in processing it they had managed before the connection was
lost. XXX: explain transaction semantics, find a decent reference.





.. rubric:: Footnotes

.. [#] There are a few other classes
       that can bestow this ability, but pb.Referenceable is the easiest to
       understand; see 'flavors' below for details on the others.
.. [#] This can be overridden, by subclassing one of
       the Serializable flavors and defining custom serialization code for your
       class. See :doc:`Passing Complex Types <pb-copyable>`  for
       details.
.. [#] The binary nature of this
       local vs. remote scheme works because you cannot give RemoteReferences to a
       third party. If you could, then your object A could go to B, B could give it to
       C, C might give it back to you, and you would be hard pressed to tell if the
       object lived in C's memory space, in B's, or if it was really your own object,
       tarnished and sullied after being handed down like a really ugly picture that
       your great aunt owned and which nobody wants but which nobody can bear to throw
       out. Ok, not really like that, but you get the idea.
.. [#] To be precise,
       the Failure will be sent if *any*  exception is raised, not just
       pb.Error-derived ones. But the server will print ugly error messages if you
       raise ones that aren't derived from pb.Error.
.. [#] 
       The naive approach
       of simply doing ``import SomeClass`` to match a remote caller who
       claims to have an object of type "SomeClass" could have nasty consequences
       for some modules that do significant operations in their ``__init__`` 
       methods (think ``telnetlib.Telnet(host='localhost', port='chargen')`` ,
       or even more powerful classes that you have available in your server program).
       Allowing a remote entity to create arbitrary classes in your namespace is
       nearly equivalent to allowing them to run arbitrary code.
       
       
       
       The :api:`twisted.spread.jelly.InsecureJelly <InsecureJelly>` 
       exception arises because the class being sent over the wire has not been
       registered with the serialization layer (known as :api:`twisted.spread.jelly <jelly>` ). The easiest way to make it possible to
       copy entire class instances over the wire is to have them inherit from :api:`twisted.spread.pb.Copyable <pb.Copyable>` , and then to use 
       ``setUnjellyableForClass(remoteClass, localClass)`` on the
       receiving side. See :doc:`Passing Complex Types <pb-copyable>` 
       for an example.
       
