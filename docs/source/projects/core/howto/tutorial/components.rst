
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

The Evolution of Finger: moving to a component based architecture
=================================================================






Introduction
------------



This is the fourth part of the Twisted tutorial :doc:`Twisted from Scratch, or The Evolution of Finger <index>` .




In this section of the tutorial, we'll move our code to a component
architecture so that adding new features is trivial.
See :doc:`Interfaces and Adapters <../components>` for a more
complete discussion of components.





Write Maintainable Code
-----------------------




In the last version, the service class was three times longer than any other
class, and was hard to understand. This was because it turned out to have
multiple responsibilities. It had to know how to access user information, by
rereading the file every half minute, but also how to display itself in a myriad
of protocols. Here, we used the component-based architecture that Twisted
provides to achieve a separation of concerns. All the service is responsible
for, now, is supporting ``getUser`` /``getUsers`` . It declares
its support via a call to ``zope.interface.implements`` . Then, adapters
are used to make this service look like an appropriate class for various things:
for supplying a finger factory to ``TCPServer`` , for supplying a
resource to site's constructor, and to provide an IRC client factory
for ``TCPClient`` .  All the adapters use are the methods
in ``FingerService`` they are declared to use:``getUser`` /``getUsers`` . We could, of course, skip the
interfaces and let the configuration code use things
like ``FingerFactoryFromService(f)`` directly. However, using
interfaces provides the same flexibility inheritance gives: future subclasses
can override the adapters.





:download:`finger19.tac <listings/finger/finger19.tac>`

.. literalinclude:: listings/finger/finger19.tac



Advantages of Latest Version
----------------------------




- Readable -- each class is short
- Maintainable -- each class knows only about interfaces
- Dependencies between code parts are minimized
- Example: writing a new ``IFingerService`` is easy





:download:`finger19a_changes.py <listings/finger/finger19a_changes.py>`

.. literalinclude:: listings/finger/finger19a_changes.py



Full source code here: 

:download:`finger19a.tac <listings/finger/finger19a.tac>`

.. literalinclude:: listings/finger/finger19a.tac







Aspect-Oriented Programming
---------------------------



At last, an example of aspect-oriented programming that isn't about logging
or timing. This code is actually useful! Watch how aspect-oriented programming
helps you write less code and have fewer dependencies!




