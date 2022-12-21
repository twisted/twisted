
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

The Basics
==========

Application
-----------

Twisted programs usually work with :py:func:`twisted.application.service.Application`.
This class usually holds all persistent configuration of a running server, such as:

- ports to bind to,
- places where connections to must be kept or attempted,
- periodic actions to do,
- and almost everything else to do with your :py:func:`Application <twisted.application.service.Application>`.

It is the root object in a tree of services implementing :py:class:`twisted.application.service.IService`.

Other howtos describe how to write custom code for ``Application``\ s, but this one describes how to use already written code (which can be part of Twisted or from a third-party Twisted plugin developer).
The Twisted distribution comes with an important tool to deal with ``Application``\ s: ``twistd(1)``.

``Application``\ s are just Python objects, which can be created and manipulated in the same ways as any other object.


twistd
------

The Twisted Daemon is a program that knows how to run :py:func:`Application <twisted.application.service.Application>`\ s.
Strictly speaking, ``twistd`` is not necessary.
Fetching the application, getting the ``IService`` component, calling ``startService()``, scheduling ``stopService()`` when the reactor shuts down, and then calling ``reactor.run()`` could be done manually.

However, ``twistd`` supplies many options which are highly useful for program set up:

- choosing a reactor (for more on reactors, see :doc:`Choosing a Reactor <choosing-reactor>`),
- logging configuration (see the :doc:`logger <logger>` documentation for more),
- daemonizing (forking to the background),
- and :doc:`more <application>`.

``twistd`` supports all Applications mentioned above -- and an additional one.
Sometimes it is convenient to write the code for building a class in straight Python.
One big source of such Python files is the :doc:`examples <../examples/index>` directory.
When a straight Python file which defines an ``Application`` object called ``application`` is used, use the ``-y`` option.

When ``twistd`` runs, it records its process id in a ``twistd.pid`` file (this can be configured via a command line switch).
In order to shutdown the ``twistd`` process, kill that pid.
The usual way to do this would be::

    kill `cat twistd.pid`

To prevent ``twistd`` from daemonizing, you can pass it the ``--no-daemon`` option (or ``-n``, in conjunction with other short options).

As always, the gory details are in the manual page.
