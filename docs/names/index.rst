:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Twisted Names
=============

.. toctree::
   :hidden:

   howto/index
   examples/index


Twisted Names is a library of DNS components for building DNS servers and clients.

It includes a client resolver API, with which you can generate queries for all the standard record types.
The client API also includes a replacement for the blocking ``gethostbyname()`` function provided by the Python stdlib socket module.

Twisted Names provides a ``twistd`` DNS server plugin which can:

  * Act as a master authoritative server
    which can read most BIND-syntax zone files as well as a simple Python-based configuration format.

  * Act as a secondary authoritative DNS server,
    which retrieves its records from a master server by zone transfer.

  * Act as a caching / forwarding nameserver
    which forwards requests to one or more upstream recursive nameservers and caches the results.

  * Or any combination of these.

The following developer guides, example scripts and API documentation will demonstrate how to use these components
and provide you with all the information you need to build your own custom DNS client or server using Twisted Names.

- :doc:`Developer guides <howto/index>`: documentation on using Twisted Names to develop your own applications
- :doc:`Examples <examples/index>`: short code examples using Twisted Names
- :api:`twisted.names <API documentation>`: Detailed API documentation for all the Twisted Names components
