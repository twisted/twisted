# Easy configuration
# makeService from finger module

def makeService(config):
    # finger on port 79
    s = service.MultiService()
    f = FingerService(config['file'])
    h = strports.service("tcp:79", IFingerFactory(f))
    h.setServiceParent(s)

    # website on port 8000
    r = resource.IResource(f)
    r.templateDirectory = config['templates']
    site = server.Site(r)
    j = strports.service("tcp:8000", site)
    j.setServiceParent(s)

    # ssl on port 443
    if config.get('ssl'):
        k = strports.service(
            "ssl:port=443:certKey=cert.pem:privateKey=key.pem", site
        )
        k.setServiceParent(s)

    # irc fingerbot
    if 'ircnick' in config:
        i = IIRCClientFactory(f)
        i.nickname = config['ircnick']
        ircserver = config['ircserver']
        b = internet.ClientService(
            endpoints.HostnameEndpoint(reactor, ircserver, 6667), i
        )
        b.setServiceParent(s)

    # Pespective Broker on port 8889
    if 'pbport' in config:
        m = internet.StreamServerEndpointService(
            endpoints.TCP4ServerEndpoint(reactor, int(config['pbport'])),
            pb.PBServerFactory(IPerspectiveFinger(f))
        )
        m.setServiceParent(s)

    return s
