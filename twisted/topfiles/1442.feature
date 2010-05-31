Added new "endpoint" interfaces in twisted.internet.interfaces, which
abstractly describe stream transport endpoints which can be listened on or
connected to.  Implementations for TCP and SSL clients and servers are present
in twisted.internet.endpoints.  Notably, client endpoints' connect() methods
return cancellable Deferreds, so code written to use them can bypass the
awkward "ClientFactory.clientConnectionFailed" and "Connector.stopConnecting"
methods, and handle errbacks from or cancel the returned deferred,
respectively.
