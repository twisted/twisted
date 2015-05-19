
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Developer Guides
================


.. toctree::
   :hidden:

   vision
   servers
   clients
   trial
   tutorial/index
   tutorial/intro
   tutorial/protocol
   tutorial/style
   tutorial/components
   tutorial/backends
   tutorial/web
   tutorial/pb
   tutorial/factory
   tutorial/client
   tutorial/library
   tutorial/configuration
   quotes
   design
   internet-overview
   reactor-basics
   ssl
   udp
   process
   defer-intro
   defer
   gendefer
   time
   threading
   producers
   choosing-reactor
   endpoints
   components
   cred
   plugin
   basics
   application
   tap
   systemd
   logger
   logging
   constants
   rdbms
   options
   dirdbm
   testing
   sendmsg
   amp
   pb
   pb-intro
   pb-usage
   pb-clients
   pb-copyable
   pb-cred
   pb-limits
   python3
   positioning
   glossary
   debug-with-emacs


- .. _core-howto-index-introduction:

  Introduction

  - :doc:`Executive summary <vision>`

    Connecting your software - and having fun too!


- .. _core-howto-index-tutorials:

  Getting Started

  - :doc:`Writing a TCP server <servers>`

    Basic network servers with Twisted.
  - :doc:`Writing a TCP client <clients>`

    And basic clients.
  - :doc:`Test-driven development with Twisted <trial>`

    Code without tests is broken by definition; Twisted makes it easy to test your network code.
  - :doc:`Tutorial: Twisted From Scratch <tutorial/index>`

    #. :doc:`The Evolution of Finger: building a simple finger service <tutorial/intro>`
    #. :doc:`The Evolution of Finger: adding features to the finger service <tutorial/protocol>`
    #. :doc:`The Evolution of Finger: cleaning up the finger code <tutorial/style>`
    #. :doc:`The Evolution of Finger: moving to a component based architecture <tutorial/components>`
    #. :doc:`The Evolution of Finger: pluggable backends <tutorial/backends>`
    #. :doc:`The Evolution of Finger: a clean web frontend <tutorial/web>`
    #. :doc:`The Evolution of Finger: Twisted client support using Perspective Broker <tutorial/pb>`
    #. :doc:`The Evolution of Finger: using a single factory for multiple protocols <tutorial/factory>`
    #. :doc:`The Evolution of Finger: a Twisted finger client <tutorial/client>`
    #. :doc:`The Evolution of Finger: making a finger library <tutorial/library>`
    #. :doc:`The Evolution of Finger: configuration and packaging of the finger service <tutorial/configuration>`

  - :doc:`Setting up the TwistedQuotes application <quotes>`
  - :doc:`Designing a Twisted application <design>`



- .. _core-howto-index-events:

  Networking and Other Event Sources

  - :doc:`Twisted Internet <internet-overview>`

    A brief overview of the ``twisted.internet`` package.
  - :doc:`Reactor basics <reactor-basics>`

    The event loop at the core of your program.
  - :doc:`Using SSL in Twisted <ssl>`

    Add some security to your network transport.
  - :doc:`UDP Networking <udp>`

    How to use Twisted's UDP implementation, including multicast and broadcast functionality.
  - :doc:`Using processes <process>`

    Launching sub-processes, the correct way.
  - :doc:`Introduction to Deferreds <defer-intro>`

    Like callback functions, only a lot better.
  - :doc:`Deferred reference <defer>`

    In-depth information on Deferreds.
  - :doc:`Generating deferreds <gendefer>`

    More about Deferreds.
  - :doc:`Scheduling <time>`

    Timeouts, repeated events, and more: when you want things to happen later.
  - :doc:`Using threads <threading>`

    Running code in threads, and interacting with Twisted in a thread-safe manner.
  - :doc:`Producers and Consumers: Efficient High-Volume Streaming <producers>`

    How to pause when buffers fill up.
  - :doc:`Choosing a reactor and GUI toolkit integration <choosing-reactor>`

    GTK+, Windows, epoll() and more: use your GUI of choice, or a faster event loop.


- .. _core-howto-index-highlevel:

  High-Level Infrastructure

  - :doc:`Getting Connected with Endpoints <endpoints>`

    Create configurable applications that support multiple transports (e.g. TCP and SSL).
  - :doc:`Interfaces and Adapters (Component Architecture) <components>`

    When inheritance isn't enough.
  - :doc:`Cred: Pluggable Authentication <cred>`

    Implementing authentication and authorization that is configurable, pluggable and re-usable.
  - :doc:`Twisted's plugin architecture <plugin>`

    A generic plugin system for extendable programs.


- .. _core-howto-index-deploying:

  Deploying Twisted Applications

  - :doc:`Helper programs and scripts (twistd, ..) <basics>`

    ``twistd`` lets you daemonize and run your application.
  - :doc:`Using the Twisted Application Framework <application>`

    Writing code that ``twistd`` can run.
  - :doc:`Writing Twisted Application Plugins for twistd <tap>`

    More powerful ``twistd`` deployment method.
  - :doc:`Deploying Twisted with systemd <systemd>`

    Use ``systemd`` to launch and monitor Twisted applications.


- .. _core-howto-index-utilities:

  Utilities

  - :doc:`Emitting and Observing Logs <logger>`

    Keep a record of what your application is up to, and inspect that record to discover interesting information.
    (You may also be interested in the :doc:`legacy logging system <logging>` if you are maintaining code written to work with older versions of Twisted.)

  - :doc:`Symbolic constants <constants>`

    enum-like constants.

  - :doc:`Twisted RDBMS support with adbapi <rdbms>`

    Using SQL with your relational database via DB-API adapters.
  - :doc:`Parsing command-line arguments <options>`

    The command-line argument parsing used by ``twistd`` .
  - :doc:`Using Dirdbm: Directory-based Storage <dirdbm>`

    A simplistic way to store data on your filesystem.
  - :doc:`Tips for writing tests for Twisted code using Trial <testing>`

    More information on writing tests.
  - :doc:`Extremely Low-Level Socket Operations <sendmsg>`

    Using wrappers for sendmsg(2) and recvmsg(2).

- .. _core-howto-index-amp:

  Asynchronous Messaging Protocol (AMP)

  - :doc:`Asynchronous Messaging Protocol Overview <amp>`

    A two-way asynchronous message passing protocol, for when HTTP isn't good enough.


- .. _core-howto-index-pb:

  Perspective Broker

  - :doc:`Twisted Spread <pb>`

    A remote method invocation (RMI) protocol: call methods on remote objects.
  - :doc:`Introduction to Perspective Broker <pb-intro>`
  - :doc:`Using Perspective Broker <pb-usage>`
  - :doc:`Managing Clients of Perspectives <pb-clients>`
  - :doc:`Passing Complex Types <pb-copyable>`
  - :doc:`Authentication with Perspective Broker <pb-cred>`
  - :doc:`PB Limits <pb-limits>`


- .. _core-howto-index-positioning:

  Positioning

  - :doc:`Twisted Positioning <positioning>`


- .. _core-howto-index-appendix:

  Appendix








  - :doc:`Porting to Python 3 <python3>`
  - :doc:`Glossary <glossary>`
  - :doc:`Tips for debugging with emacs <debug-with-emacs>`
