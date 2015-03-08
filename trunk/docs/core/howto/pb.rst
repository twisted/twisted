
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Overview of Twisted Spread
==========================







Perspective Broker (affectionately known as "PB" ) is an
asynchronous, symmetric [#]_ network protocol for secure,
remote method calls and transferring of objects. PB is "translucent, not transparent" , meaning that it is very visible and obvious to see the
difference between local method calls and potentially remote method calls,
but remote method calls are still extremely convenient to make, and it is
easy to emulate them to have objects which work both locally and
remotely.




PB supports user-defined serialized data in return values, which can be
either copied each time the value is returned, or "cached" : only copied
once and updated by notifications.




PB gets its name from the fact that access to objects is through a "perspective" . This means that when you are responding to a remote
method call, you can establish who is making the call.





Rationale
---------



No other currently existing protocols have all the properties of PB at the
same time. The particularly interesting combination of attributes, though, is
that PB is flexible and lightweight, allowing for rapid development, while
still powerful enough to do two-way method calls and user-defined data
types.




It is important to have these attributes in order to allow for a protocol
which is extensible. One of the facets of this flexibility is that PB can
integrate an arbitrary number of services could be aggregated over a single
connection, as well as publish and call new methods on existing objects
without restarting the server or client.





.. rubric:: Footnotes

.. [#] There is a negotiation phase
       for the ``banana``  serialization protocol with particular roles for listener and initiator, so it's not
       *completely*  symmetric, but after the connection is fully established,
       the protocol is completely symmetrical.
