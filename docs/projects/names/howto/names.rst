:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Creating and working with a names (DNS) server
==============================================
A Names server can be perform three basic operations:

- act as a recursive server, forwarding queries to other servers
- perform local caching of recursively discovered records
- act as the authoritative server for a domain

Creating a non-authoritative server
-----------------------------------
The first two of these are easy, and you can create a server that performs them
with the command ``twistd -n dns --recursive --cache`` .
You may wish to run this as root since it will try to bind to UDP port 53.  Try
performing a lookup with it, ``dig twistedmatrix.com @127.0.0.1`` .

Creating an authoritative server
--------------------------------
To act as the authority for a domain, two things are necessary: the address
of the machine on which the domain name server will run must be registered
as a nameserver for the domain; and the domain name server must be
configured to act as the authority.  The first requirement is beyond the
scope of this howto and will not be covered.

To configure Names to act as the authority
for ``example-domain.com`` , we first create a zone file for
this domain.

:download:`example-domain.com <listings/names/example-domain.com>`

.. literalinclude:: listings/names/example-domain.com

Next, run the command ``twistd -n dns --pyzone example-domain.com`` .  Now try querying the domain locally (again, with
dig): ``dig -t any example-domain.com @127.0.0.1`` .

Names can also read a traditional, BIND-syntax zone file.  Specify these
with the ``--bindzone`` parameter.  The $GENERATE and $INCLUDE
directives are not yet supported.
