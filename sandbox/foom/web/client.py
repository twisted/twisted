class HTTPClient(basic.LineReceiver):
    """A client for HTTP 1.0

    Notes:
    You probably want to send a 'Host' header with the name of
    the site you're connecting to, in order to not break name
    based virtual hosting.
    """
    length = None
    firstLine = 1
    __buffer = ''

    def sendCommand(self, command, path):
        self.transport.write('%s %s HTTP/1.0\r\n' % (command, path))

    def sendHeader(self, name, value):
        self.transport.write('%s: %s\r\n' % (name, value))

    def endHeaders(self):
        self.transport.write('\r\n')

    def lineReceived(self, line):
        if self.firstLine:
            self.firstLine = 0
            try:
                version, status, message = line.split(None, 2)
            except ValueError:
                # sometimes there is no message
                version, status = line.split(None, 1)
                message = ""
            self.handleStatus(version, status, message)
            return
        if line:
            key, val = line.split(':', 1)
            val = val.lstrip()
            self.handleHeader(key, val)
            if key.lower() == 'content-length':
                self.length = int(val)
        else:
            self.handleEndHeaders()
            self.setRawMode()

    def connectionLost(self, reason):
        self.handleResponseEnd()

    def handleResponseEnd(self):
        if self.__buffer != None:
            b = self.__buffer
            self.__buffer = None
            self.handleResponse(b)
    
    def handleResponsePart(self, data):
        self.__buffer += data

    def connectionMade(self):
        pass

    handleStatus = handleHeader = handleEndHeaders = lambda *args: None

    def rawDataReceived(self, data):
        if self.length is not None:
            data, rest = data[:self.length], data[self.length:]
            self.length -= len(data)
        else:
            rest = ''
        self.handleResponsePart(data)
        if self.length == 0:
            self.handleResponseEnd()
            self.setLineMode(rest)


