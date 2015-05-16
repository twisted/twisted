def prettyRequest(server, requestName):
    return server.makeRequest(requestName
                              ).addCallback(
        lambda result: ', '.join(result.asList())
        ).addErrback(
        lambda failure: failure.printTraceback())
