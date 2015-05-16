
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Twisted Glossary
================









.. _core-howto-glossary-adaptee:

adaptee





  
  An object that has been adapted, also called "original" .  See :ref:`Adapter <core-howto-glossary-adapter>` .

.. _core-howto-glossary-adapter:



:api:`twisted.python.components.Adapter <Adapter>` 



  
  An object whose sole purpose is to implement an Interface for another object.
  See :doc:`Interfaces and Adapters <components>` .

.. _core-howto-glossary-application:



:api:`twisted.application.service.Application <Application>` 



  
  A :api:`twisted.application.service.Application <twisted.application.service.Application>` .  There are
  HOWTOs on :doc:`creating and manipulating <basics>` them as a
  system-administrator, as well as :doc:`using <application>` them in
  your code.

.. _core-howto-glossary-avatar:

Avatar





  
  (from :ref:`Twisted Cred <core-howto-glossary-cred>` ) business logic for specific user.
  For example, in :ref:`PB <core-howto-glossary-pb>` these are perspectives, in POP3 these
  are mailboxes, and so on.

.. _core-howto-glossary-banana:



:api:`twisted.spread.banana.Banana <Banana>` 



  
  The low-level data marshalling layer of :ref:`Twisted Spread <core-howto-glossary-spread>` .
  See :api:`twisted.spread.banana <twisted.spread.banana>` .

.. _core-howto-glossary-broker:



:api:`twisted.spread.pb.Broker <Broker>` 



  
  A :api:`twisted.spread.pb.Broker <twisted.spread.pb.Broker>` , the object request
  broker for :ref:`Twisted Spread <core-howto-glossary-spread>` .

.. _core-howto-glossary-cache:

cache





  
  A way to store data in readily accessible place for later reuse. Caching data
  is often done because the data is expensive to produce or access. Caching data
  risks being stale, or out of sync with the original data.

.. _core-howto-glossary-component:

component





  
  A special kind of (persistent) :api:`twisted.python.components.Adapter <Adapter>` that works with a :api:`twisted.python.components.Componentized <twisted.python.components.Componentized>` .  See also :doc:`Interfaces and Adapters <components>` .

.. _core-howto-glossary-componentized:



:api:`twisted.python.components.Componentized <Componentized>` 



  
  A Componentized object is a collection of information, separated
  into domain-specific or role-specific instances, that all stick
  together and refer to each other.
  Each object is an :api:`twisted.python.components.Adapter <Adapter>` , which, in the
  context of Componentized, we call "components" .  See also :doc:`Interfaces and Adapters <components>` .

.. _core-howto-glossary-conch:



:api:`twisted.conch <conch>` 



  Twisted's SSH implementation.

.. _core-howto-glossary-connector:

Connector





  
  Object used to interface between client connections and protocols, usually
  used with a :api:`twisted.internet.protocol.ClientFactory <twisted.internet.protocol.ClientFactory>` 
  to give you control over how a client connection reconnects.  See :api:`twisted.internet.interfaces.IConnector <twisted.internet.interfaces.IConnector>` and :doc:`Writing Clients <clients>` .

.. _core-howto-glossary-consumer:

Consumer





  
  An object that consumes data from a :ref:`Producer <core-howto-glossary-producer>` .  See 
  :api:`twisted.internet.interfaces.IConsumer <twisted.internet.interfaces.IConsumer>` .

.. _core-howto-glossary-cred:

Cred





  
  Twisted's authentication API, :api:`twisted.cred <twisted.cred>` .  See 
  :doc:`Introduction to Twisted Cred <cred>` and 
  :doc:`Twisted Cred usage <pb-cred>` .

.. _core-howto-glossary-credentials:

credentials





  
  A username/password, public key, or some other information used for
  authentication.

.. _core-howto-glossary-credential-checker:

credential checker





  
  Where authentication actually happens.  See 
  :api:`twisted.cred.checkers.ICredentialsChecker <ICredentialsChecker>` .

.. _core-howto-glossary-cvstoys:

CVSToys





  A nifty set of tools for CVS, available at `http://twistedmatrix.com/users/acapnotic/wares/code/CVSToys/ <http://twistedmatrix.com/users/acapnotic/wares/code/CVSToys/>`_ .

.. _core-howto-glossary-daemon:

Daemon





  
  A background process that does a job or handles client requests.
  *Daemon* is a Unix term; *service* is the Windows equivalent.

.. _core-howto-glossary-deferred:



:api:`twisted.internet.defer.Deferred <Deferred>` 



  
  A instance of :api:`twisted.internet.defer.Deferred <twisted.internet.defer.Deferred>` , an
  abstraction for handling chains of callbacks and error handlers
  ("errbacks" ).
  See the :doc:`Deferring Execution <defer>` HOWTO.

.. _core-howto-glossary-enterprise:

Enterprise





  
  Twisted's RDBMS support.  It contains :api:`twisted.enterprise.adbapi <twisted.enterprise.adbapi>` for asynchronous access to any
  standard DB-API 2.0 module. See :doc:`Introduction to Twisted Enterprise <rdbms>` for more details.

.. _core-howto-glossary-errback:

errback





  
  A callback attached to a :ref:`Deferred <core-howto-glossary-deferred>` with
  ``.addErrback`` to handle errors.

.. _core-howto-glossary-factory:



:api:`twisted.internet.protocol.Factory <Factory>` 



  
  In general, an object that constructs other objects.  In Twisted, a Factory
  usually refers to a :api:`twisted.internet.protocol.Factory <twisted.internet.protocol.Factory>` , which constructs
  :ref:`Protocol <core-howto-glossary-protocol>` instances for incoming or outgoing
  connections.  See :doc:`Writing Servers <servers>` and :doc:`Writing Clients <clients>` .

.. _core-howto-glossary-failure:



:api:`twisted.python.failure.Failure <Failure>` 



  
  Basically, an asynchronous exception that contains traceback information;
  these are used for passing errors through asynchronous callbacks.

.. _core-howto-glossary-im:

im





  
  Abbreviation of "(Twisted) :ref:`Instance Messenger <core-howto-glossary-instancemessenger>`" .

.. _core-howto-glossary-instancemessenger:

Instance Messenger





  
  Instance Messenger is a multi-protocol chat program that comes with
  Twisted.  It can communicate via TOC with the AOL servers, via IRC, as well as
  via :ref:`PB <core-howto-glossary-perspectivebroker>` with 
  :ref:`Twisted Words <core-howto-glossary-words>` .  See :api:`twisted.words.im <twisted.words.im>` .

.. _core-howto-glossary-interface:

Interface





  
  A class that defines and documents methods that a class conforming to that
  interface needs to have.  A collection of core :api:`twisted.internet <twisted.internet>` interfaces can
  be found in :api:`twisted.internet.interfaces <twisted.internet.interfaces>` .  See also :doc:`Interfaces and Adapters <components>` .

.. _core-howto-glossary-jelly:

Jelly






  The serialization layer for :ref:`Twisted Spread <core-howto-glossary-spread>` , although it
  can be used separately from Twisted Spread as well.  It is similar in purpose
  to Python's standard ``pickle`` module, but is more
  network-friendly, and depends on a separate marshaller (:ref:`Banana <core-howto-glossary-banana>` , in most cases).  See :api:`twisted.spread.jelly <twisted.spread.jelly>` .

.. _core-howto-glossary-manhole:

Manhole





  
  A debugging/administration interface to a Twisted application.

.. _core-howto-glossary-microdom:

Microdom





  
  A partial DOM implementation using :ref:`SUX <core-howto-glossary-sux>` .  It is simple and
  pythonic, rather than strictly standards-compliant.  See :api:`twisted.web.microdom <twisted.web.microdom>` .

.. _core-howto-glossary-names:

Names





  Twisted's DNS server, found in :api:`twisted.names <twisted.names>` .

.. _core-howto-glossary-nevow:

Nevow





  The successor to :ref:`Woven <core-howto-glossary-woven>` ; available from `Divmod <http://launchpad.net/nevow>`_ .

.. _core-howto-glossary-pb:

PB





  
  Abbreviation of ":ref:`Perspective Broker <core-howto-glossary-perspectivebroker>`" .

.. _core-howto-glossary-perspectivebroker:

Perspective Broker





  
  The high-level object layer of Twisted :ref:`Spread <core-howto-glossary-spread>` ,
  implementing semantics for method calling and object copying, caching, and
  referencing.  See :api:`twisted.spread.pb <twisted.spread.pb>` .

.. _core-howto-glossary-portal:

Portal





  
  Glues :ref:`credential checkers <core-howto-glossary-credential-checker>` and 
  :ref:`realm <core-howto-glossary-realm>` s together.

.. _core-howto-glossary-producer:

Producer





  
  An object that generates data a chunk at a time, usually to be processed by a
  :ref:`Consumer <core-howto-glossary-consumer>` .  See 
  :api:`twisted.internet.interfaces.IProducer <twisted.internet.interfaces.IProducer>` .

.. _core-howto-glossary-protocol:



:api:`twisted.internet.protocol.Protocol <Protocol>` 



  
  In general each network connection has its own Protocol instance to manage
  connection-specific state.  There is a collection of standard
  protocol implementations in :api:`twisted.protocols <twisted.protocols>` .  See
  also :doc:`Writing Servers <servers>` and :doc:`Writing Clients <clients>` .

.. _core-howto-glossary-psu:

PSU





  There is no PSU.

.. _core-howto-glossary-reactor:

Reactor





  
  The core event-loop of a Twisted application.  See 
  :doc:`Reactor Basics <reactor-basics>` .

.. _core-howto-glossary-reality:

Reality





  See ":ref:`Twisted Reality <core-howto-glossary-twistedreality>`"

.. _core-howto-glossary-realm:

realm





  
  (in :ref:`Twisted Cred <core-howto-glossary-cred>` ) stores :ref:`avatars <core-howto-glossary-avatar>` 
  and perhaps general business logic.  See 
  :api:`twisted.cred.portal.IRealm <IRealm>` .

.. _core-howto-glossary-resource:



:api:`twisted.web.resource.Resource <Resource>` 



  
  A :api:`twisted.web.resource.Resource <twisted.web.resource.Resource>` , which are served
  by Twisted Web.  Resources can be as simple as a static file on disk, or they
  can have dynamically generated content.

.. _core-howto-glossary-service:

Service





  
  A :api:`twisted.application.service.Service <twisted.application.service.Service>` .  See :doc:`Application howto <application>` for a description of how they
  relate to :ref:`Applications <core-howto-glossary-application>` .

.. _core-howto-glossary-spread:

Spread





  Twisted Spread is
  Twisted's remote-object suite.  It consists of three layers: :ref:`Perspective Broker <core-howto-glossary-perspectivebroker>` , :ref:`Jelly <core-howto-glossary-jelly>` 
  and :ref:`Banana. <core-howto-glossary-banana>` See :doc:`Writing Applications with Perspective Broker <pb>` .

.. _core-howto-glossary-sux:

SUX





  *S* mall *U* ncomplicated *X* ML, Twisted's simple XML
  parser written in pure Python.  See :api:`twisted.web.sux <twisted.web.sux>` .

.. _core-howto-glossary-tac:

TAC





  A *T* wisted *A* pplication *C* onfiguration is a Python
  source file, generally with the *.tac* extension, which defines
  configuration to make an application runnable using ``twistd`` .

.. _core-howto-glossary-tap:

TAP





  *T* wisted *A* pplication *P* ickle (no longer supported), or simply just a*T* wisted *AP* plication.  A serialised application that was created
  with ``mktap`` (no longer supported) and runnable by ``twistd`` .  See:doc:`Using the Utilities <basics>` .

.. _core-howto-glossary-trial:

Trial





  :api:`twisted.trial <twisted.trial>` , Twisted's unit-testing framework,
  based on the ``unittest`` standard library module.  See also :doc:`Writing tests for Twisted code <testing>` .

.. _core-howto-glossary-twistedmatrixlaboratories:

Twisted Matrix Laboratories





  The team behind Twisted.  `http://twistedmatrix.com/ <http://twistedmatrix.com/>`_ .

.. _core-howto-glossary-twistedreality:

Twisted Reality





  
  In days of old, the Twisted Reality multiplayer text-based interactive-fiction
  system was the main focus of Twisted Matrix Labs; Twisted, the general networking
  framework, grew out of Reality's need for better network functionality. Twisted
  Reality has been superseded by the `Imaginary <http://launchpad.net/imaginary>`_ project.

.. _core-howto-glossary-usage:



:api:`twisted.python.usage <usage>` 



  The :api:`twisted.python.usage <twisted.python.usage>` module, a replacement for
  the standard ``getopt`` module for parsing command-lines which is much
  easier to work with.  See :doc:`Parsing command-lines <options>` .

.. _core-howto-glossary-words:

Words





  Twisted Words is a multi-protocol chat server that uses the :ref:`Perspective Broker <core-howto-glossary-perspectivebroker>` protocol as its native
  communication style.  See :api:`twisted.words <twisted.words>` .

.. _core-howto-glossary-woven:

Woven





  *W* eb *O* bject *V* isualization *En* vironment.
  A templating system previously, but no longer, included with Twisted.  Woven
  has largely been superseded by `Divmod Nevow <http://launchpad.net/nevow>`_ .





