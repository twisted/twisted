
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Writing a twistd Plugin
=======================

This document describes adding subcommands to the ``twistd`` command,
as a way to facilitate the deployment of your applications.

The target audience of this document are those that have developed a Twisted application which needs a command line-based deployment mechanism.

There are a few prerequisites to understanding this document:

- A basic understanding of the Twisted Plugin System (i.e., the :py:mod:`twisted.plugin` module) is necessary,
  however, step-by-step instructions will be given.
  Reading :doc:`The Twisted Plugin System <plugin>` is recommended,
  in particular the "Extending an Existing Program" section.
- The :doc:`Application <application>` infrastructure is used in ``twistd`` plugins;
  in particular, you should know how to expose your program's functionality as a Service.
- In order to parse command line arguments, the ``twistd`` plugin mechanism relies on ``twisted.python.usage`` ,
  which is documented in :doc:`Using usage.Options <options>` .

Goals
-----

After reading this document,
the reader should be able to expose their Service-using application as a subcommand of ``twistd`` ,
taking into consideration whatever was passed on the command line.

Alternatives to twistd Plugins
------------------------------

The major alternative to the twistd plugin mechanism is the ``.tac`` file,
which is a simple script to be used with the twistd ``-y/--python`` parameter.
The twistd plugin mechanism exists to offer a more extensible command-line-driven interface to your application.
For more information on ``.tac`` files,
see the document :doc:`Using the Twisted Application Framework <application>` .

Creating the Plugin
-------------------

The following directory structure is assumed of your project:

- ``MyProject`` - Top level directory

  - ``myproject`` - Python package

    - ``__init__.py``

During development of your project,
Twisted plugins can be loaded from a special directory in your project,
assuming your top level directory ends up in :data:`sys.path`.
Create a directory named ``twisted`` containing a directory named ``plugins`` ,
and add a file named ``myproject_plugin.py`` to it.
This file will contain your plugin.
Note that you must *not* add any ``__init__.py`` files to this directory structure,
and the plugin file should *not* be named ``myproject.py``
(because that would conflict with your project's module name).

In this file, define an object which *provides* the interfaces :py:class:`twisted.plugin.IPlugin`
and :py:class:`twisted.application.service.IServiceMaker` .

The ``tapname`` attribute of your IServiceMaker provider will be used as the subcommand name in a command like ``twistd [subcommand] [args...]`` ,
and the ``options`` attribute
(which should be a :py:class:`usage.Options <twisted.python.usage.Options>` subclass)
will be used to parse the given args.


.. code-block:: python

    from zope.interface import implementer

    from twisted.python import usage
    from twisted.plugin import IPlugin
    from twisted.application.service import IServiceMaker
    from twisted.application import internet

    from myproject import MyFactory


    class Options(usage.Options):
        optParameters = [["port", "p", 1235, "The port number to listen on."]]


    @implementer(IServiceMaker, IPlugin)
    class MyServiceMaker(object):
        tapname = "myproject"
        description = "Run this! It'll make your dog happy."
        options = Options

        def makeService(self, options):
            """
            Construct a TCPServer from a factory defined in myproject.
            """
            return internet.TCPServer(int(options["port"]), MyFactory())


    # Now construct an object which *provides* the relevant interfaces
    # The name of this variable is irrelevant, as long as there is *some*
    # name bound to a provider of IPlugin and IServiceMaker.
    serviceMaker = MyServiceMaker()


Now running ``twistd --help`` should print ``myproject`` in the list of available subcommands,
followed by the description that we specified in the plugin.
``twistd -n myproject`` would,
assuming we defined a ``MyFactory`` factory inside ``myproject`` ,
start a listening server on port 1235 with that factory.


Using ``cred`` with your TAP
----------------------------

Twisted ships with a robust authentication framework to use with your application.
If your server needs authentication functionality,
and you haven't read about :doc:`twisted.cred <cred>` yet,
read up on it first.

If you are building a twistd plugin and you want to support a wide variety of authentication patterns,
Twisted provides an easy-to-use mixin for your Options subclass:
:py:class:`strcred.AuthOptionMixin <twisted.cred.strcred.AuthOptionMixin>` .
The following code is an example of using this mixin:

.. code-block:: python

    from twisted.cred import credentials, portal, strcred
    from twisted.python import usage
    from twisted.plugin import IPlugin
    from twisted.application.service import IServiceMaker
    from myserver import myservice


    class ServerOptions(usage.Options, strcred.AuthOptionMixin):
        # This part is optional; it tells AuthOptionMixin what
        # kinds of credential interfaces the user can give us.
        supportedInterfaces = (credentials.IUsernamePassword,)

        optParameters = [
            ["port", "p", 1234, "Server port number"],
            ["host", "h", "localhost", "Server hostname"]]


    @implementer(IServiceMaker, IPlugin)
    class MyServerServiceMaker(object):
        tapname = "myserver"
        description = "This server does nothing productive."
        options = ServerOptions

        def makeService(self, options):
            """Construct a service object."""
            # The realm is a custom object that your server defines.
            realm = myservice.MyServerRealm(options["host"])

            # The portal is something Cred can provide, as long as
            # you have a list of checkers that you'll support. This
            # list is provided my AuthOptionMixin.
            portal = portal.Portal(realm, options["credCheckers"])

            # OR, if you know you might get multiple interfaces, and
            # only want to give your application one of them, you
            # also have that option with AuthOptionMixin:
            interface = credentials.IUsernamePassword
            portal = portal.Portal(realm, options["credInterfaces"][interface])

            # The protocol factory is, like the realm, something you implement.
            factory = myservice.ServerFactory(realm, portal)

            # Finally, return a service that will listen for connections.
            return internet.TCPServer(int(options["port"]), factory)


    # As in our example above, we have to construct an object that
    # provides the IPlugin and IServiceMaker interfaces.
    serviceMaker = MyServerServiceMaker()


Now that you have your TAP configured to support any authentication we can throw at it,
you're ready to use it.
Here is an example of starting your server using the ``/etc/passwd`` file for authentication.
(Clearly, this won't work on servers with shadow passwords.)


.. code-block:: console

    $ twistd myserver --auth passwd:/etc/passwd


For a full list of cred plugins supported,
see :py:mod:`twisted.plugins` ,
or use the command-line help:

.. code-block:: console

    $ twistd myserver --help-auth
    $ twistd myserver --help-auth-type passwd


Deploy your Application Using Python Packages
---------------------------------------------

To deploy your application one possibility is to wrap it up in a Python package.
For this you need to write a special file ``setup.py``, which contains metadata
of the package. You would have to extend the layout of your files like this:


- ``MyProject`` - Top level directory

  - ``setup.py`` - Description file for the package

    - ``myproject`` - Python package

      - ``__init__.py``

    - ``twisted``

      - ``plugins``

        - ``myproject_plugins.py`` - Dropin file containing the actual plugin


.. code-block:: python
    :caption: a minimal ``setup.py`` file

    from setuptools import setup, find_packages

    setup(
        name='MyApplication',
        version='0.1dev',
        # it is necesary to extend the found package list with the twisted.plugin
        # directory. It cannot be automatically detected, because it should not
        # contain a __init__.py file.
        packages=find_packages() + ['twisted.plugins'],
        install_requires=[
            'twisted',
        ],
    )


To create the Python package from the directory the standard setup tools can be used:

.. code-block:: console

    $ python3 setup.py sdist


This command creates a ``dist`` directory in your project folder with the
compressed archive file ``MyApplication-0.1dev.tar.gz``. This archive contains
all the code and additional files if specified. This file can be copied and used
for deployment.

To install the application just use pip. It will also install all requirements
specified in ``setup.py``.

.. code-block:: console

    $ pip install MyApplication-0.1dev.tar.gz


For more information about packaging in Python have a look at the `official
Python packaging user guide <https://packaging.python.org/tutorials/packaging-projects/>`_ or
`hitchhiker's guide to packaging
<https://the-hitchhikers-guide-to-packaging.readthedocs.io/>`_.

Conclusion
----------

You should now be able to

- Create a twistd plugin
- Incorporate authentication into your plugin
- Use it from your development environment
- Install it correctly and use it in deployment
