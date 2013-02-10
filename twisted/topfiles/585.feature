twisted.internet.interfaces.IWriteFileTransport is a new interface providing a
writeFile method on TCP transports, to send the content of the file over the
transport, possibly using sendfile(2) if available.
