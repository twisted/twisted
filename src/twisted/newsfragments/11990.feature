twisted.names.server.DNSServerFactory can respond with the SOA record in the authority section, when there exists an authoritative resolver that is parent of a QNAME, and the response is NXDOMAIN.
                                                                                   
twisted.names.server.DNSServerFactory sets the AA flag, when there exists an authoritative resolver that is parent of a QNAME, and the response is NXDOMAIN.
