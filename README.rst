Twisted
#######

|gitter|_
|rtd|_
|pypi|_
|ci|_

For information on changes in this release, see the `NEWS <NEWS.rst>`_ file.


What is this?
-------------

Twisted is an event-based framework for internet applications, supporting Python 3.6+.
It includes modules for many different purposes, including the following:

- ``twisted.web``: HTTP clients and servers, HTML templating, and a WSGI server
- ``twisted.conch``: SSHv2 and Telnet clients and servers and terminal emulators
- ``twisted.words``: Clients and servers for IRC, XMPP, and other IM protocols
- ``twisted.mail``: IMAPv4, POP3, SMTP clients and servers
- ``twisted.positioning``: Tools for communicating with NMEA-compatible GPS receivers
- ``twisted.names``: DNS client and tools for making your own DNS servers
- ``twisted.trial``: A unit testing framework that integrates well with Twisted-based code.

Twisted supports all major system event loops -- ``select`` (all platforms), ``poll`` (most POSIX platforms), ``epoll`` (Linux), ``kqueue`` (FreeBSD, macOS), IOCP (Windows), and various GUI event loops (GTK+2/3, Qt, wxWidgets).
Third-party reactors can plug into Twisted, and provide support for additional event loops.


Installing
----------

To install the latest version of Twisted using pip::

  $ pip install twisted

Additional instructions for installing this software are in `the installation instructions <INSTALL.rst>`_.


Documentation and Support
-------------------------

Twisted's documentation is available from the `Twisted Matrix website <https://twistedmatrix.com/documents/current/>`_.
This documentation contains how-tos, code examples, and an API reference.

Help is also available on the `Twisted mailing list <https://mail.python.org/mailman3/lists/twisted.python.org/>`_.

There is also an IRC channel, ``#twisted``,
on the `Libera.Chat <https://libera.chat/>`_ network.
A web client is available at `web.libera.chat <https://web.libera.chat/>`_.


Unit Tests
----------

Twisted has a comprehensive test suite, which can be run by ``tox``::

  $ tox -l                       # to view all test environments
  $ tox -e nocov                 # to run all the tests without coverage
  $ tox -e withcov               # to run all the tests with coverage
  $ tox -e alldeps-withcov-posix # install all dependencies, run tests with coverage on POSIX platform


You can test running the test suite under the different reactors with the ``TWISTED_REACTOR`` environment variable::

  $ env TWISTED_REACTOR=epoll tox -e alldeps-withcov-posix

Some of these tests may fail if you:

* don't have the dependencies required for a particular subsystem installed,
* have a firewall blocking some ports (or things like Multicast, which Linux NAT has shown itself to do), or
* run them as root.


Static Code Checkers
--------------------

You can ensure that code complies to Twisted `coding standards <https://twistedmatrix.com/documents/current/core/development/policy/coding-standard.html>`_::

  $ tox -e lint   # run pre-commit to check coding stanards
  $ tox -e mypy   # run MyPy static type checker to check for type errors

Or, for speed, use pre-commit directly::

  $ pipx run pre-commit run


Copyright
---------

All of the code in this distribution is Copyright (c) 2001-2024 Twisted Matrix Laboratories.

Twisted is made available under the MIT license.
The included `LICENSE <LICENSE>`_ file describes this in detail.


Warranty
--------

  THIS SOFTWARE IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND, EITHER
  EXPRESSED OR IMPLIED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
  OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.  THE ENTIRE RISK AS
  TO THE USE OF THIS SOFTWARE IS WITH YOU.

  IN NO EVENT WILL ANY COPYRIGHT HOLDER, OR ANY OTHER PARTY WHO MAY MODIFY
  AND/OR REDISTRIBUTE THE LIBRARY, BE LIABLE TO YOU FOR ANY DAMAGES, EVEN IF
  SUCH HOLDER OR OTHER PARTY HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH
  DAMAGES.

Again, see the included `LICENSE <LICENSE>`_ file for specific legal details.


.. |pypi| image:: https://img.shields.io/pypi/v/twisted.svg
.. _pypi: https://pypi.python.org/pypi/twisted

.. |gitter| image:: https://img.shields.io/gitter/room/twisted/twisted.svg
.. _gitter: https://gitter.im/twisted/twisted

.. |ci| image:: https://github.com/twisted/twisted/actions/workflows/test.yaml/badge.svg
.. _ci: https://github.com/twisted/twisted

.. |rtd| image:: https://readthedocs.org/projects/twisted/badge/?version=latest&style=flat
.. _rtd: https://docs.twistedmatrix.com
