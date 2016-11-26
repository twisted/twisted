
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Historical Documents
====================

Here are documents which contain no pertinent information or documentation.
People from the Twisted team have published them, and they serve as interesting land marks and thoughts.
Please don't look here for documentation -- however, if you are interested in the history of Twisted, or want to quote from these documents, feel free.
Remember, however -- the documents here may contain wrong information -- they are not updated as Twisted is, to keep their historical value intact.


2003
----

Python Community Conference
~~~~~~~~~~~~~~~~~~~~~~~~~~~

These papers were part of the `Python Community Conference <http://python.org/pycon/>`_ (PyCon) in March of 2003.

..  Do we want to link slides too?

`Generalization of Deferred Execution in Python <2003/pycon/deferex.html>`_

  A deceptively simple architectural challenge faced by many
  multi-tasking applications is gracefully doing nothing.  Systems that
  must wait for the results of a long-running process, network message, or
  database query while continuing to perform other tasks must establish
  conventions for the semantics of waiting.  The simplest of these is
  blocking in a thread, but it has significant scalability problems.  In
  asynchronous frameworks, the most common approach is for long-running
  methods to accept a callback that will be executed when the command
  completes.  These callbacks will have different signatures depending on
  the nature of the data being requested, and often, a great deal of code
  is necessary to glue one portion of an asynchronous networking system to
  another.  Matters become even more complicated when a developer wants to
  wait for two different events to complete, requiring the developer to
  "juggle" the callbacks and create a third, mutually incompatible
  callback type to handle the final result.

  This paper describes the mechanism used by the Twisted framework for
  waiting for the results of long-running operations.  This mechanism,
  the ``Deferred`` , handles the often-neglected problems of
  error handling, callback juggling, inter-system communication and code
  readability.

`Applications of the Twisted Framework <2003/pycon/applications/applications.html>`_

  Two projects developed using the Twisted framework are described;
  one, Twisted.names, which is included as part of the Twisted
  distribution, a domain name server and client API, and one, Pynfo, which
  is packaged separately, a network information robot.

`Twisted Conch: SSH in Python with Twisted <2003/pycon/conch/conch.html>`_

  Conch is an implementation of the Secure Shell Protocol (currently
  in the IETF standarization process). Secure Shell (or SSH) is a popular
  protocol for remote shell access, file management and port forwarding
  protected by military-grade security. SSH supports multiple encryption and
  compression protocols for the wire transports, and a flexible system of
  multiplexed channels on top. Conch uses the Twisted networking framework
  to supply a library which can be used to implement both SSH clients and
  servers. In addition, it also contains several ready made client programs,
  including a drop-in replacement for the OpenSSH program from the OpenBSD
  project.

`The Lore Document Generation Framework <2003/pycon/lore/lore.html>`_

  Lore is a documentation generation system which uses a limited
  subset of XHTML, together with some class attributes, as its source
  format. This allows for lower barrier of entry than many other similar
  systems, since HTML authoring tools are plentiful as is knowledge of
  HTML writing. As an added advantage, the source format is viewable
  directly, so that even if Lore is not available the documentation is
  useful. It currently outputs LaTeX and HTML, which allows for most
  use-cases.

`Perspective Broker: "Translucent"  Remote Method calls in Twisted <2003/pycon/pb/pb.html>`_

  One of the core services provided by the Twisted networking
  framework is "Perspective Broker" , which provides a clean, secure,
  easy-to-use Remote Procedure Call (RPC) mechanism. This paper explains the
  novel features of PB, describes the security model and its implementation,
  and provides brief examples of usage.

`Managing the Release of a Large Python Project <2003/pycon/releasing/releasing.html>`_

  Twisted is a Python networking framework. At last count, the
  project contains nearly 60,000 lines of effective code (not comments or
  blank lines). When preparing a release, many details must be checked, and
  many steps must be followed. We describe here the technologies and tools
  we use, and explain how we built tools on top of them which help us make
  releasing as painless as possible.

`Twisted Reality: A Flexible Framework for Virtual Worlds <2003/pycon/twisted-reality/twisted-reality.html>`_

  Flexibly modelling virtual worlds in object-oriented languages has
  historically been difficult; the issues arising from multiple
  inheritance and order-of-execution resolution have limited the
  sophistication of existing object-oriented simulations. Twisted
  Reality avoids these problems by reifying both actions and
  relationships, and avoiding inheritance in favor of automated
  composition through adapters and interfaces.


Previously
----------

- `The paper Glyph and Moshe presented in IPC10 <ipc10paper.html>`_
- `The errata published in IPC10 against the paper. <ipc10errata.html>`_
- `A paper Moshe wrote about Twisted and Debian. <twisted-debian.html>`_
