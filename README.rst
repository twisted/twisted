Twisted 15.4.0
==============

Release Codename:

    "Trial By Fire"

For information on what's new in Twisted 15.4.0, see the NEWS file that comes with the distribution.


What is this?
-------------

Twisted is an event-based framework for internet applications, supporting Python 2.7 and Python 3.3+.
It includes modules for many different purposes, including the following:

- ``twisted.web``: HTTP clients and servers, HTML templating, and a WSGI server
- ``twisted.conch``: SSHv2 and Telnet clients and servers and terminal emulators
- ``twisted.words``: Clients and servers for IRC, XMPP, and other IM protocols
- ``twisted.mail``: IMAPv4, POP3, SMTP clients and servers
- ``twisted.positioning``: Tools for communicating with NMEA-compatible GPS recievers
- ``twisted.names``: DNS client and tools for making your own DNS servers
- ``twisted.trial``: A unit testing framework that integrates well with Twisted-based code.

Twisted supports all major system event loops -- ``select`` (all platforms), ``poll`` (most POSIX platforms), ``epoll`` (Linux), ``kqueue`` (FreeBSD, OS X), IOCP (Windows), and various GUI event loops (GTK+2/3, QT, wxWidgets).
Third-party reactors can plug into Twisted, and provide support for additional event loops.


Installing
----------

To install the latest version of Twisted using pip::

  $ pip install twisted

You can install optional dependencies for specific functionality in Twisted (such as TLS or serial support) by using our `setuptools extras <http://twistedmatrix.com/documents/current/installation/howto/optional.html>`.
To install Twisted with TLS dependencies, use::

  $ pip install twisted[tls]

Additional instructions for installing this software are in ``INSTALL``.


Documentation and Support
-------------------------

Twisted's documentation is available from the `Twisted Matrix website <http://twistedmatrix.com/documents/current/>`.
This documentation contains how-tos, code examples, and an API reference.

Help is also available on the `Twisted mailing list <http://twistedmatrix.com/cgi-bin/mailman/listinfo/twisted-python>`

There is also a pair of very lively IRC channels, ``#twisted`` (for general Twisted questions) and ``#twisted.web`` (for Twisted Web), on chat.freenode.net.


Unit Tests
----------

Twisted has a comprehensive test suite, which can be run by ``tox``::

  $ tox -l # to view all test environments
  $ tox -e py27-tests # to run the tests for

Some of these tests may fail if you:

* don't have the dependencies required for a particular subsystem installed,
* have a firewall blocking some ports (or things like Multicast, which Linux NAT has shown itself to do), or
* run them as root.


Copyright
---------

All of the code in this distribution is Copyright (c) 2001-2015 Twisted Matrix Laboratories.

Twisted is made available under the MIT license.
The included ``LICENSE`` file describes this in detail.


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

Again, see the included ``LICENSE`` file for specific legal details.
