
class Driver:
    """abstract base class for database drivers. This isolated database specific code
    (even through there shouldn't be any) that the python DBAPI 2.0 implementations
    expose.
    """
    def connect(self, server, database, username, password, host, port):
        """maps args into the correct connect format. Should return
        a connection object.
        """
        print "NOT IMPLEMENTED"

    def execute(self, connection, request):
        """uses the right exceptions for the driver.
        Should return 0 or 1"""
        print "NOT IMPLEMENTED"



class DriverSybase:
    """Driver for the Sybase database interface. This driver doesn't seem to scale well
    with multiple threads or connections. Available from:

        http://object-craft.com.au/projects/sybase/sybase/sybase.html

    """
    def __init__(self):
        print "Creating Sybase database driver"
        import Sybase
        self.driver = Sybase

    def connect(self, server, database, username, password, host, port):
        """Connect to a Sybase database server
        """
        connection = None
        try:
            connection = self.driver.connect(
                server, 
                username, 
                password, 
                database=database
                )
        except self.driver.InternalError, e:
            print "unable to connect to database: %s" % repr(e)
        return connection

    def execute(self, connection, request):
        """Execute a request
        """
        try:
            result = request.execute(connection)
            return 1
        except self.driver.InternalError, e:
            text = "SQL ERROR:\n"
            self.error = e[0][1]
            for k in self.error.keys():
                text = text +  "    %s: %s\n" % (k, self.error[k])
            print text
            request.error = text
            return 0


class DriverInterbase:
    """Driver for the Interbase gvib database interface. This driver
    is only able to connect to local Interbase database instances -
    it actually takes the full path to a _file_ as the database
    argument. Available from:

        http://clientes.netvisao.pt/luiforra/ib/index.html

    """
    def __init__(self):
        print "Creating Interbase gvib Database driver"        
        import gvib
        from gvib import gvibExceptions                    
        self.driver = gvib
        self.exceptions = gvibExceptions
        
    def connect(self, server, database, username, password, host, port):
        """Connect to an Interbase database server
        """

        connection = None
        try:
            connection = self.driver.connect( database, username, password )
            print "Connected to Interbase"
        except self.exceptions.StandardError, e:
            print "Interbase error: %s" % e
        return connection
 
    def execute(self, connection, request):
        """Execute a request
        """
        try:
            result = request.execute(connection)
            return 1
        except gvibExceptions.StandardError, e:
            print "Interbase error: %s" % e.args
            request.error = e
            return 0
 

class DriverPostgres:
    """PoPy driver for the Postres database interface. Available from:

        http://popy.sourceforge.net/
        
    """
    def __init__(self):
        print "Creating Postgres PoPy Database driver"
        import PoPy
        self.driver = PoPy
        
    def connect(self, server, database, username, password, host, port):
        """Connect to a Postgres database server
        """
        connection = None
        try:
            connection = self.driver.connect("user=%s dbname=%s port=%s host=%s" % (username, database, port, host) )
        except self.driver.DatabaseError, e:
            print "unable to connect to database: %s" % repr(e)
        return connection

    def execute(self, connection, request):
        """Execute a request
        """
        try:
            result = request.execute(connection)
            return 1
        except self.driver.DatabaseError, e:
            print "SQL ERROR: %s" % e
            request.error = e
            return 0


databaseDrivers = {
    "sybase":DriverSybase,
    "interbase":DriverInterbase,
    "postgres":DriverPostgres
    }


def getDriver(driverName):
    global databaseDrivers
    if databaseDrivers.has_key(driverName):
        return databaseDrivers[driverName]()
    else:
        return None
