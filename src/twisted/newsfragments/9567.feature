ThreadedResolver.getHostByName now uses socket.getaddrinfo as the underneath function to resolve DNS name for the sake of IPv6 compatibility.
