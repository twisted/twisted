twisted.internet.endpoints.HostnameEndpoint now uses the passed reactor's
implementation of twisted.internet.interfaces.IReactorPluggableResolver to
resolve hostnames rather than its own deferToThread/getaddrinfo wrapper; this
makes its hostname resolution pluggable via a public API.
