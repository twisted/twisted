twisted.web.client.HTTPConnectionPool passes the repr() of the endpoint to the client protocol factory, and the protocol factory adds that to its own repr(). This makes logs more useful.
