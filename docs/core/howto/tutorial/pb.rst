
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

The Evolution of Finger: Twisted client support using Perspective Broker
========================================================================






Introduction
------------



This is the seventh part of the Twisted tutorial :doc:`Twisted from Scratch, or The Evolution of Finger <index>` .




In this part, we add a Perspective Broker service to the finger application
so that Twisted clients can access the finger server. Perspective Broker is
introduced in depth in its own :ref:`section <core-howto-index-pb>` of the
core howto index.





Use Perspective Broker
----------------------



We add support for perspective broker, Twisted's native remote object
protocol. Now, Twisted clients will not have to go through XML-RPCish
contortions to get information about users.





:download:`finger21.tac <listings/finger/finger21.tac>`

.. literalinclude:: listings/finger/finger21.tac


A simple client to test the perspective broker finger:





:download:`fingerPBclient.py <listings/finger/fingerPBclient.py>`

.. literalinclude:: listings/finger/fingerPBclient.py

