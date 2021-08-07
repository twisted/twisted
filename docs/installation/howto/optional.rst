:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Installing Optional Dependencies
================================

This document describes the optional dependencies that Twisted supports.
The dependencies are python packages that Twisted's developers have found useful either for developing Twisted itself or for developing Twisted applications.

The intended audience of this document is someone who is familiar with installing optional dependencies using `pip`_.

If you are unfamiliar with the installation of optional dependencies, the `python packaging tutorial`_ can show you how.
For a deeper explanation of what optional dependencies are and how they are declared, please see the `setuptools documentation`_.

The following optional dependencies are supported:

tls
   Packages that are needed to work with TLS:

   * pyOpenSSL_
   * service_identity_
   * idna_

conch
   Packages for working with conch/SSH:

   * pyasn1_
   * cryptography_
   * bcrypt_
   * appdirs_

conch_nacl
   ``conch`` options and PyNaCl_ to support Ed25519 keys
   on systems with OpenSSL < 1.1.1b.

serial
   The pyserial_ package to work with serial data.
   On Windows, this also requires pywin32_.

http2
   Packages needed for HTTP/2 support:

   * h2_
   * priority_

contextvars
   The contextvars_ backport package to provide `context variables`_ support
   for Python versions before 3.7.

all
   Extras ``tls``, ``conch``, ``serial``, ``http2``, ``contextvars``,
   and platform-specific interfacing such as pyobjc_ for Objective-C on macOS
   and pywin32_ for Windows.

dev_release
   Packages used in Twisted's release process:

   * towncrier_
   * pydoctor_
   * Sphinx_, sphinx-rtd-theme_ and readthedocs-sphinx-ext_

dev
   Packages that aid in the development of Twisted itself,
   including those in ``all`, ``dev_release`` and the following:

   * pyflakes_
   * python-subunit_
   * twistedchecker_
   * coverage_

mypy
   Type checking facilities, including ``dev`` packages,
   ``conch_nacl``, as well as the following:

   * mypy_
   * mypy-zope_
   * types-setuptools_
   * types-pyOpenSSL_

.. _pip: https://pip.pypa.io
.. _python packaging tutorial:
   https://packaging.python.org/en/latest/installing.html#examples
.. _setuptools documentation:
   https://setuptools.readthedocs.io/en/stable/userguide/dependency_management.html#optional-dependencies

.. _pyOpenSSL: https://pypi.org/project/pyOpenSSL
.. _service_identity: https://pypi.org/project/service_identity
.. _idna: https://pypi.org/project/idna

.. _pyasn1: https://pypi.org/project/pyasn1
.. _cryptography: https://pypi.org/project/cryptography
.. _bcrypt: https://pypi.org/project/bcrypt
.. _appdirs: https://pypi.org/project/appdirs

.. _PyNaCl: https://pypi.python.org/pypi/PyNaCl

.. _pyserial: https://pypi.org/project/pyserial
.. _pywin32: https://pypi.org/project/pywin32

.. _h2: https://pypi.org/project/h2
.. _priority: https://pypi.org/project/priority

.. _contextvars: https://pypi.org/project/contextvars
.. _context variables: https://docs.python.org/3/library/contextvars.html

.. _pyobjc: https://pypi.org/project/pyobjc

.. _mypy: https://pypi.org/project/mypy
.. _mypy-zope: https://pypi.org/project/mypy-zope
.. _types-setuptools: https://pypi.org/project/types-setuptools
.. _types-pyOpenSSL: https://pypi.org/project/types-pyOpenSSL

.. _towncrier: https://pypi.org/project/towncrier
.. _pydoctor: https://pypi.org/project/pydoctor
.. _Sphinx: https://pypi.org/project/Sphinx
.. _sphinx-rtd-theme: https://pypi.org/project/sphinx-rtd-theme
.. _readthedocs-sphinx-ext: https://pypi.org/project/readthedocs-sphinx-ext

.. _pyflakes: https://pypi.org/project/pyflakes
.. _python-subunit: https://pypi.org/project/python-subunit
.. _twistedchecker: https://pypi.org/project/twistedchecker
.. _coverage: https://pypi.org/project/coverage
