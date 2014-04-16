twisted.names.root.Resolver now accepts a resolverFactory argument, which makes
it possible to control how root.Resolver performs iterative queries to
authoritative nameservers.