"""Parser for inetd.conf files"""

# Various exceptions
class InvalidConfError(Exception):
    """Invalid configuration file"""


class InvalidInetdConfError(InvalidConfError):
    """Invalid inetd.conf file"""


class InvalidServicesConfError(InvalidConfError):
    """Invalid services file"""


class UnknownService(Exception):
    """Unknown service name"""


class SimpleConfFile:
    """Simple configuration file parser superclass.

    Filters out comments and empty lines (which includes lines that only 
    contain comments).
    """
    
    commentChar = '#'
    
    def parseFile(self, file):
        """Parse a configuration file"""
        for line in file.readlines():
            # Strip out comments
            comment = line.find(self.commentChar)
            if comment != -1:
                line = line[:comment]

            # Strip whitespace
            line = line.strip()

            # Skip empty lines (and lines which only contain comments)
            if not line:
                continue

            self.parseLine(line)

    def parseLine(self, line):
        """Override this."""


class InetdService:
    name = None
    port = None
    socketType = None
    protocol = None
    wait = None
    user = None
    group = None
    program = None
    programArgs = None
    
    def __init__(self, name, port, socketType, protocol, wait, user, group,
                 program, programArgs):
        self.name = name
        self.port = port
        self.socketType = socketType
        self.protocol = protocol
        self.wait = wait
        self.user = user
        self.group = group
        self.program = program
        self.programArgs = programArgs


class InetdConf(SimpleConfFile):
    """Configuration parser for a traditional UNIX inetd(8)"""
    
    def __init__(self, knownServices = None):
        self.services = []
        
        if knownServices is None:
            knownServices = ServicesConf()
            knownServices.parseFile()
        self.knownServices = knownServices

    def parseLine(self, line):
        """Parse an inetd.conf file.

        Implemented from the description in the Debian inetd.conf man page.
        """
        # Split the line into fields
        fields = line.split()

        # Raise an error if there aren't enough fields
        if len(fields) < 6:
            raise InvalidInetdConfError, 'Invalid line: ' + repr(line)

        # Put the fields into variables
        serviceName, socketType, protocol, wait, user, program = fields[:6]
        programArgs = fields[6:]
        
        # Extract user (and optional group)
        user, group = (user.split('.') + [None])[:2]

        # Find the port for a service
        port = self.knownServices.services.get((serviceName, protocol), None)
        if not port:
            # FIXME: Should this be discarded/ignored, rather than throwing
            #        an exception?
            raise UnknownService, "Unknown service: %s (%s)" \
                                  % (serviceName, protocol)

        self.services.append(InetdService(serviceName, port, socketType,
                                          protocol, wait, user, group, program,
                                          programArgs))
            
            
class ServicesConf(SimpleConfFile):
    """/etc/services parser
    
    Instance variables:
        * self.services: dict mapping service names to (port, protocol) tuples.
    """
    
    def __init__(self):
        self.services = {}

    def parseFile(self, file=None):
        if file is None:
            file = open('/etc/services')
        SimpleConfFile.parseFile(self, file)

    def parseLine(self, line):
        fields = line.split()
        if len(fields) < 2:
            raise InvalidServicesConfError, 'Invalid line:' + repr(line)

        name, portAndProtocol = fields[:2]
        aliases = fields[2:]
        
        try:
            port, protocol = portAndProtocol.split('/')
            port = int(port)
        except:
            raise InvalidServicesConfError, 'Invalid port/protocol:' + \
                                            repr(portAndProtocol)

        self.services[(name, protocol)] = port
        for alias in aliases:
            self.services[(alias, protocol)] = port



