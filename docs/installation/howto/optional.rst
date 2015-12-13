
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

* **dev** - packages that aid in the development of Twisted itself.
    * `TwistedChecker`_
    * `pyflakes`_
    * `twisted-dev-tools`_
    * `python-subunit`_
    * `Sphinx`_
    * `pydoctor`_

* **tls** - packages that are needed to work with TLS.
    * `pyOpenSSL`_
    * `service_identity`_
    * `idna`_

* **conch** - packages for working with conch/SSH.
    * `gmpy`_
    * `pyasn1`_
    * `cryptography`_

* **soap** - the `SOAPpy`_ package to work with SOAP.

* **serial** - the `pyserial`_ package to work with serial data.

* **all_non_platform** - installs **tls**, **conch**, **soap**, and **serial** options.

* **osx_platform** - **all_non_platform** options and `pyobjc`_ to work with Objective-C apis.

* **windows_platform** - **all_non_platform** options and `pypiwin32`_ to work with Windows's apis.

.. _pip: https://pip.pypa.io/en/latest/quickstart.html
.. _TwistedChecker: https://pypi.python.org/pypi/TwistedChecker
.. _pyflakes: https://pypi.python.org/pypi/pyflakes
.. _twisted-dev-tools: https://pypi.python.org/pypi/twisted-dev-tools
.. _python-subunit: https://pypi.python.org/pypi/python-subunit
.. _Sphinx: https://pypi.python.org/pypi/Sphinx/1.3b1
.. _pydoctor: https://pypi.python.org/pypi/pydoctor
.. _pyOpenSSL: https://pypi.python.org/pypi/pyOpenSSL
.. _service_identity: https://pypi.python.org/pypi/service_identity
.. _gmpy: https://pypi.python.org/pypi/gmpy/1.17
.. _pyasn1: https://pypi.python.org/pypi/pyasn1
.. _cryptography: https://pypi.python.org/pypi/cryptography
.. _SOAPpy: https://pypi.python.org/pypi/SOAPpy
.. _pyserial: https://pypi.python.org/pypi/pyserial
.. _pyobjc: https://pypi.python.org/pypi/pyobjc
.. _pypiwin32: https://pypi.python.org/pypi/pypiwin32
.. _`setuptools documentation`: https://pythonhosted.org/setuptools/setuptools.html#declaring-extras-optional-features-with-their-own-dependencies
.. _`python packaging tutorial`: https://packaging.python.org/en/latest/installing.html#examples
.. _idna: https://pypi.python.org/pypi/idna
