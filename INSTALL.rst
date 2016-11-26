Installing Twisted
==================

Installation Requirements
-------------------------

To install Twisted, you need:

- Python 2.7 (full functionality) or 3.3/3.4/3.5 (subset of functionality).

- `setuptools <https://pypi.python.org/pypi/setuptools>`_
  (installed automatically if you use pip).

- `Zope Interface <https://pypi.python.org/pypi/zope.interface>`_  3.6.0 or newer.
  Zope Interface 4.0 or newer is required for Python 3.
  Installing via pip will automatically download a suitable Zope Interface.

- On Windows `pywin32 <https://pypi.python.org/pypi/pypiwin32>`_ is required.
  Build 219 or later is highly recommended for reliable operation (this is already included in ActivePython).

We also have `setuptools extras <http://twistedmatrix.com/documents/current/installation/howto/optional.html>`_ for automatically installing optional packages used by Twisted.


Installing Twisted
------------------

To install the latest version of Twisted using pip::

  $ pip install twisted

You can install optional dependencies for specific functionality in Twisted (such as TLS or serial support) by using our setuptools extras (see above).

As an example, to install Twisted with the TLS dependencies, use::

  $ pip install twisted[tls]

Additionally, there are packages available in the repositories of:

- Debian and Ubuntu as ``python-twisted`` for Python 2.
- FreeBSD as ``py-twisted`` for Python 2.
- Arch as ``python-twisted`` for Python 2.
- Fedora and RHEL as ``python-twisted`` for Python 2.
