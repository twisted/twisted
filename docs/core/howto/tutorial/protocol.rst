
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

The Evolution of Finger: adding features to the finger service
==============================================================






Introduction
------------



This is the second part of the Twisted tutorial :doc:`Twisted from Scratch, or The Evolution of Finger <index>` .




In this section of the tutorial, our finger server will continue to sprout
features: the ability for users to set finger announces, and using our finger
service to send those announcements on the web, on IRC and over XML-RPC.
Resources and XML-RPC are introduced in the Web Applications portion of
the :doc:`Twisted Web howto <../../../web/howto/index>` . More examples
using :api:`twisted.words.protocols.irc <twisted.words.protocols.irc>` can be found
in :doc:`Writing a TCP Client <../clients>` and
the :doc:`Twisted Words examples <../../../words/examples/index>` .





Setting Message By Local Users
------------------------------



Now that port 1079 is free, maybe we can use it with a different
server, one which will let people set their messages. It does
no access control, so anyone who can login to the machine can
set any message. We assume this is the desired behavior in
our case. Testing it can be done by simply:





.. code-block:: console

    
    % nc localhost 1079   # or telnet localhost 1079
    moshez
    Giving a tutorial now, sorry!
    ^D





:download:`finger12.tac <listings/finger/finger12.tac>`

.. literalinclude:: listings/finger/finger12.tac


This program has two protocol-factory-TCPServer pairs, which are
both child services of the application.  Specifically,
the :api:`twisted.application.service.Service.setServiceParent <setServiceParent>` 
method is used to define the two TCPServer services as children
of ``application`` , which implements :api:`twisted.application.service.IServiceCollection <IServiceCollection>` .  Both
services are thus started with the application.






Use Services to Make Dependencies Sane
--------------------------------------



The previous version had the setter poke at the innards of the
finger factory. This strategy is usually not a good idea: this version makes
both factories symmetric by making them both look at a single
object. Services are useful for when an object is needed which is
not related to a specific network server. Here, we define a common service
class with methods that will create factories on the fly. The service
also contains methods the factories will depend on.




The factory-creation methods, ``getFingerFactory`` 
and ``getFingerSetterFactory`` , follow this pattern:





#. Instantiate a generic server
   factory, ``twisted.internet.protocol.ServerFactory`` .
#. Set the protocol class, just like our factory class would have.
#. Copy a service method to the factory as a function attribute.  The
   function won't have access to the factory's ``self`` , but
   that's OK because as a bound method it has access to the
   service's ``self`` , which is what it needs.
   For ``getUser`` , a custom method defined in the service gets
   copied.  For ``setUser`` , a standard method of
   the ``users`` dictionary is copied.



Thus, we stopped subclassing: the service simply puts useful methods and
attributes inside the factories. We are getting better at protocol design:
none of our protocol classes had to be changed, and neither will have to
change until the end of the tutorial.




As an application service, this new finger service implements the :api:`twisted.application.service.IService <IService>` interface and
can be started and stopped in a standardized manner. We'll make use of this in
the next example.





:download:`finger13.tac <listings/finger/finger13.tac>`

.. literalinclude:: listings/finger/finger13.tac


Most application services will want to use the :api:`twisted.application.service.Service <Service>` base class, which implements
all the generic ``IService`` behavior.





Read Status File
----------------



This version shows how, instead of just letting users set their
messages, we can read those from a centrally managed file. We cache
results, and every 30 seconds we refresh it. Services are useful
for such scheduled tasks.



listings/finger/etc.users



:download:`finger14.tac <listings/finger/finger14.tac>`

.. literalinclude:: listings/finger/finger14.tac


Since this version is reading data from a file (and refreshing the data 
every 30 seconds), there is no ``FingerSetterFactory`` and thus 
nothing listening on port 1079.




Here we override the standard :api:`twisted.application.service.Service.startService <startService>` 
and :api:`twisted.application.service.Service.stopService <stopService>` hooks in
the Finger service, which is set up as a child service of the
application in the last line of the code. ``startService`` 
calls ``_read`` , the function responsible for reading the
data; ``reactor.callLater`` is then used to schedule it to
run again after thirty seconds every time it is
called. ``reactor.callLater`` returns an object that lets us
cancel the scheduled run in ``stopService`` using
its ``cancel`` method.





Announce on Web, Too
--------------------



The same kind of service can also produce things useful for other
protocols. For example, in twisted.web, the factory itself
(``Site`` ) is almost
never subclassed — instead, it is given a resource, which
represents the tree of resources available via URLs. That hierarchy is
navigated by ``Site`` 
and overriding it dynamically is possible with ``getChild`` .




To integrate this into the Finger application (just because we can), we set
up a new TCPServer that calls the ``Site`` factory and retrieves resources via a
new function of ``FingerService`` named ``getResource`` .
This function specifically returns a ``Resource`` object with an overridden ``getChild`` method.





:download:`finger15.tac <listings/finger/finger15.tac>`

.. literalinclude:: listings/finger/finger15.tac



Announce on IRC, Too
--------------------



This is the first time there is client code. IRC clients often act a lot like
servers: responding to events from the network.  The reconnecting client factory
will make sure that severed links will get re-established, with intelligent
tweaked exponential back-off algorithms. The IRC client itself is simple: the
only real hack is getting the nickname from the factory
in ``connectionMade`` .





:download:`finger16.tac <listings/finger/finger16.tac>`

.. literalinclude:: listings/finger/finger16.tac


``FingerService`` now has another new
function, ``getIRCbot`` , which returns
the ``ReconnectingClientFactory`` .  This factory in turn will
instantiate the ``IRCReplyBot`` protocol.  The IRCBot is
configured in the last line to connect
to ``irc.freenode.org`` with a nickname
of ``fingerbot`` .




By
overriding ``irc.IRCClient.connectionMade`` , ``IRCReplyBot`` 
can access the ``nickname`` attribute of the factory that
instantiated it.





Add XML-RPC Support
-------------------



In Twisted, XML-RPC support is handled just as though it was
another resource. That resource will still support GET calls normally
through render(), but that is usually left unimplemented. Note
that it is possible to return deferreds from XML-RPC methods.
The client, of course, will not get the answer until the deferred
is triggered.





:download:`finger17.tac <listings/finger/finger17.tac>`

.. literalinclude:: listings/finger/finger17.tac


Instead of a web browser, we can test the XMLRPC finger using a simple
client based on Python's built-in ``xmlrpclib`` , which will access
the resource we've made available at ``localhost/RPC2`` .





:download:`fingerXRclient.py <listings/finger/fingerXRclient.py>`

.. literalinclude:: listings/finger/fingerXRclient.py

