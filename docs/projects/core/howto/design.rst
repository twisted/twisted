
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Designing Twisted Applications
==============================






Goals
-----



This document describes how a good Twisted application is structured. It
should be useful for beginning Twisted developers who want to structure their
code in a clean, maintainable way that reflects current best practices.




Readers will want to be familiar with writing :doc:`servers <servers>` and :doc:`clients <clients>` using Twisted.





Example of a modular design: TwistedQuotes
------------------------------------------



``TwistedQuotes`` is a very simple plugin which is a great
demonstration of
Twisted's power.  It will export a small kernel of functionality -- Quote of
the Day -- which can be accessed through every interface that Twisted supports:
web pages, e-mail, instant messaging, a specific Quote of the Day protocol, and
more.





Set up the project directory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~



See the description of :doc:`setting up the TwistedQuotes example <quotes>` .





A Look at the Heart of the Application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~




:download:`quoters.py <listings/TwistedQuotes/quoters.py>`

.. literalinclude:: listings/TwistedQuotes/quoters.py


This code listing shows us what the Twisted Quotes system is all about.  The
code doesn't have any way of talking to the outside world, but it provides a
library which is a clear and uncluttered abstraction: "give me the quote of the day" . 




Note that this module does not import any Twisted functionality at all!  The
reason for doing things this way is integration.  If your "business objects" are not stuck to your user interface, you can make a module that
can integrate those objects with different protocols, GUIs, and file formats.
Having such classes provides a way to decouple your components from each other,
by allowing each to be used independently.




In this manner, Twisted itself has minimal impact on the logic of your
program.  Although the Twisted "dot products" are highly interoperable,
they
also follow this approach.  You can use them independently because they are not
stuck to each other.  They communicate in well-defined ways, and only when that
communication provides some additional feature.  Thus, you can use :api:`twisted.web <twisted.web>` with :api:`twisted.enterprise <twisted.enterprise>` , but neither requires the other, because
they are integrated around the concept of :doc:`Deferreds <defer>` .




Your Twisted applications should follow this style as much as possible.
Have (at least) one module which implements your specific functionality,
independent of any user-interface code.  




Next, we're going to need to associate this abstract logic with some way of
displaying it to the user.  We'll do this by writing a Twisted server protocol,
which will respond to the clients that connect to it by sending a quote to the
client and then closing the connection.  Note: don't get too focused on the
details of this -- different ways to interface with the user are 90% of what
Twisted does, and there are lots of documents describing the different ways to
do it.





:download:`quoteproto.py <listings/TwistedQuotes/quoteproto.py>`

.. literalinclude:: listings/TwistedQuotes/quoteproto.py


This is a very straightforward ``Protocol`` implementation, and the
pattern described above is repeated here.  The Protocol contains essentially no
logic of its own, just enough to tie together an object which can generate
quotes (a ``Quoter`` ) and an object which can relay
bytes to a TCP connection (a ``Transport`` ).  When a
client connects to this server, a ``QOTD`` instance is
created, and its ``connectionMade`` method is called.




The ``QOTDFactory`` 's role is to specify to the
Twisted framework how to create a ``Protocol`` instance
that will handle the connection.  Twisted will not instantiate a ``QOTDFactory`` ; you will do that yourself later, in a ``twistd`` plug-in.




Note: you can read more specifics of ``Protocol`` and ``Factory`` in the :doc:`Writing Servers <servers>` HOWTO.




Once we have an abstraction -- a ``Quoter`` -- and we have a
mechanism to connect it to the network -- the ``QOTD`` protocol -- the
next thing to do is to put the last link in the chain of functionality between
abstraction and user.  This last link will allow a user to choose a ``Quoter`` and configure the protocol. Writing this configuration is
covered in the :doc:`Application HOWTO <application>` .



