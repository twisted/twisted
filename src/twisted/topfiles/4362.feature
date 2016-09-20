A new resolver interface, twisted.internet.interfaces.INameResolver, provides a
getaddrinfo-style interface for name resolution, making it possible to use the
reactor resolver interface for IPv6-capable applications.  This is one step
along the way to doing asynchronous name resolution with HostnameEndpoint.