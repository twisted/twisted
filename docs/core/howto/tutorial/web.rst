
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

The Evolution of Finger: a web frontend
=======================================






Introduction
------------



This is the sixth part of the Twisted tutorial :doc:`Twisted from Scratch, or The Evolution of Finger <index>` .




In this part, we demonstrate adding a web frontend using
simple :api:`twisted.web.resource.Resource <twisted.web.resource.Resource>` 
objects: ``UserStatusTree`` , which will
produce a listing of all users at the base URL (``/`` ) of our
site; ``UserStatus`` , which gives the status
of each user at the location ``/username`` ;
and ``UserStatusXR`` , which exposes an XMLRPC
interface to ``getUser`` 
and ``getUsers`` functions at the
URL ``/RPC2`` .




In this example we construct HTML segments manually. If the web interface
was less trivial, we would want to use more sophisticated web templating and
design our system so that HTML rendering and logic were clearly separated.





:download:`finger20.tac <listings/finger/finger20.tac>`

.. literalinclude:: listings/finger/finger20.tac

