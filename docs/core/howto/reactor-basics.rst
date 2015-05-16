
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Reactor Overview
================






This HOWTO introduces the Twisted reactor, describes the basics of the
reactor and links to the various reactor interfaces.

  
    



Reactor Basics
--------------


    
The reactor is the core of the event loop within Twisted -- the loop
which drives applications using Twisted. The event loop is a programming
construct that waits for and dispatches events or messages in a program.
It works by calling some internal or external "event provider", which
generally blocks until an event has arrived, and then calls the relevant
event handler ("dispatches the event"). The reactor provides basic
interfaces to a number of services, including network communications,
threading, and event dispatching.


    



For information about using the reactor and the Twisted event loop, see:


    




- the event dispatching howtos: :doc:`Scheduling <time>` and :doc:`Using Deferreds <defer>` ;
- the communication howtos: :doc:`TCP servers <servers>` , :doc:`TCP clients <clients>` , :doc:`UDP networking <udp>` and :doc:`Using processes <process>` ; and
- :doc:`Using threads <threading>` .


    


There are multiple implementations of the reactor, each
modified to provide better support for specialized features
over the default implementation.  More information about these
and how to use a particular implementation is available via
:doc:`Choosing a Reactor <choosing-reactor>` .

    
    



Twisted applications can use the interfaces in :api:`twisted.application.service <twisted.application.service>` to configure and run the
application instead of using
boilerplate reactor code. See :doc:`Using Application <application>` for an introduction to
Application.


    



Using the reactor object
------------------------


    
You can get to the :api:`twisted.internet.reactor <reactor>` object using the following code:





.. code-block:: python

    
    from twisted.internet import reactor



    
The reactor usually implements a set of interfaces, but 
depending on the chosen reactor and the platform, some of
the interfaces may not be implemented:

    




- :api:`twisted.internet.interfaces.IReactorCore <IReactorCore>` : Core (required) functionality.
- :api:`twisted.internet.interfaces.IReactorFDSet <IReactorFDSet>` : Use FileDescriptor objects.
- :api:`twisted.internet.interfaces.IReactorProcess <IReactorProcess>` : Process management. Read the 
  :doc:`Using Processes <process>` document for
  more information.
- :api:`twisted.internet.interfaces.IReactorSSL <IReactorSSL>` : SSL networking support.
- :api:`twisted.internet.interfaces.IReactorTCP <IReactorTCP>` : TCP networking support. More information
  can be found in the :doc:`Writing Servers <servers>` 
  and :doc:`Writing Clients <clients>` documents.
- :api:`twisted.internet.interfaces.IReactorThreads <IReactorThreads>` : Threading use and management. More
  information can be found within :doc:`Threading In Twisted <threading>` .
- :api:`twisted.internet.interfaces.IReactorTime <IReactorTime>` : Scheduling interface.  More information
  can be found within :doc:`Scheduling Tasks <time>` .
- :api:`twisted.internet.interfaces.IReactorUDP <IReactorUDP>` : UDP networking support. More information
  can be found within :doc:`UDP Networking <udp>` .
- :api:`twisted.internet.interfaces.IReactorUNIX <IReactorUNIX>` : UNIX socket support.
- :api:`twisted.internet.interfaces.IReactorSocket <IReactorSocket>` : Third-party socket support.

  

