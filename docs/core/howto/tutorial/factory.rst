
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

The Evolution of Finger: using a single factory for multiple protocols
======================================================================






Introduction
------------



This is the eighth part of the Twisted tutorial :doc:`Twisted from Scratch, or The Evolution of Finger <index>` .




In this part, we add HTTPS support to our web frontend, showing how to have a
single factory listen on multiple ports. More information on using SSL in
Twisted can be found in the :doc:`SSL howto <../ssl>` .





Support HTTPS
-------------



All we need to do to code an HTTPS site is just write a context factory (in
this case, which loads the certificate from a certain file) and then use the
twisted.application.internet.SSLServer method. Note that one factory (in this
case, a site) can listen on multiple ports with multiple protocols.





:download:`finger22.py <listings/finger/finger22.py>`

.. literalinclude:: listings/finger/finger22.py

