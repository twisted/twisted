twisted.web.client.Agent now uses HostnameEndpoint internally; as a
consequence, it now supports IPv6, as well as making connections faster and
more reliably to hosts that have more than one DNS name.
