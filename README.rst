Twisted 17.1.0
==============

|pypi|
|coverage|
|travis|
|appveyor|

.. code::

    <hawkowl> we have always been at war with 16.7

For information on what's new in Twisted 17.1.0, see the `NEWS <NEWS>`_ file that comes with the distribution.


What is this?
-------------

Twisted is an event-based framework for internet applications, supporting Python 2.7 and Python 3.3+.
It includes modules for many different purposes, including the following:

- ``twisted.web``: HTTP clients and servers, HTML templating, and a WSGI server
- ``twisted.conch``: SSHv2 and Telnet clients and servers and terminal emulators
- ``twisted.words``: Clients and servers for IRC, XMPP, and other IM protocols
- ``twisted.mail``: IMAPv4, POP3, SMTP clients and servers
- ``twisted.positioning``: Tools for communicating with NMEA-compatible GPS receivers
- ``twisted.names``: DNS client and tools for making your own DNS servers
- ``twisted.trial``: A unit testing framework that integrates well with Twisted-based code.

Twisted supports all major system event loops -- ``select`` (all platforms), ``poll`` (most POSIX platforms), ``epoll`` (Linux), ``kqueue`` (FreeBSD, OS X), IOCP (Windows), and various GUI event loops (GTK+2/3, QT, wxWidgets).
Third-party reactors can plug into Twisted, and provide support for additional event loops.


Installing
----------

To install the latest version of Twisted using pip::

  $ pip install twisted

Additional instructions for installing this software are in `the installation instructions <INSTALL.rst>`_.


Documentation and Support
-------------------------

Twisted's documentation is available from the `Twisted Matrix website <http://twistedmatrix.com/documents/current/>`_.
This documentation contains how-tos, code examples, and an API reference.

Help is also available on the `Twisted mailing list <http://twistedmatrix.com/cgi-bin/mailman/listinfo/twisted-python>`_.

There is also a pair of very lively IRC channels, ``#twisted`` (for general Twisted questions) and ``#twisted.web`` (for Twisted Web), on ``chat.freenode.net``.


Unit Tests
----------

Twisted has a comprehensive test suite, which can be run by ``tox``::

  $ tox -l            # to view all test environments
  $ tox -e py27-tests # to run the tests for Python 2.7
  $ tox -e py34-tests # to run the tests for Python 3.4


You can test running the test suite under the different reactors with the ``TWISTED_REACTOR`` environment variable::

  $ env TWISTED_REACTOR=epoll tox -e py27-tests


Some of these tests may fail if you:

* don't have the dependencies required for a particular subsystem installed,
* have a firewall blocking some ports (or things like Multicast, which Linux NAT has shown itself to do), or
* run them as root.


Copyright
---------

All of the code in this distribution is Copyright (c) 2001-2017 Twisted Matrix Laboratories.

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


.. |coverage| image:: https://codecov.io/github/twisted/twisted/coverage.svg?branch=trunk
.. _coverage: https://codecov.io/github/twisted/twisted

.. |pypi| image:: http://img.shields.io/pypi/v/twisted.svg
.. _pypi: https://pypi.python.org/pypi/twisted

.. |travis| image:: https://travis-ci.org/twisted/twisted.svg?branch=trunk
.. _travis https://travis-ci.org/twisted/twisted

.. |appveyor| image:: https://ci.appveyor.com/api/projects/status/x4oyqtl9cqc2i2l8
.. _appveyor https://ci.appveyor.com/project/adiroiban/twisted
