twisted.web.proxy.ProxyClient (and all of its users in twisted.web.proxy) will now close HTTP connections that they initiate if the incoming connection to the proxy dies before receiving a response.
