Added a new interface, twisted.internet.interfaces.IHostnameResolver, which is
an improvement to twisted.internet.interfaces.IResolverSimple that supports
resolving multiple addresses as well as resolving IPv6 addresses.  This is a
native, asynchronous, Twisted analogue to getaddrinfo.
