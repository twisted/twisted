
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

The Evolution of Finger: a Twisted finger client
================================================






Introduction
------------



This is the ninth part of the Twisted tutorial :doc:`Twisted from Scratch, or The Evolution of Finger <index>` .




In this part, we develop a client for the finger server: a proxy finger
server which forwards requests to another finger server.





Finger Proxy
------------



Writing new clients with Twisted is much like writing new servers.
We implement the protocol, which just gathers up all the data, and
give it to the factory. The factory keeps a deferred which is triggered
if the connection either fails or succeeds. When we use the client,
we first make sure the deferred will never fail, by producing a message
in that case. Implementing a wrapper around client which just returns
the deferred is a common pattern.  While less flexible than
using the factory directly, it's also more convenient.






:download:`fingerproxy.tac <listings/finger/fingerproxy.tac>`

.. literalinclude:: listings/finger/fingerproxy.tac

