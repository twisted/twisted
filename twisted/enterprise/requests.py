

class Request:
    """base class for database requests to be executed in dbconnection threads.
    the method 'execute' will be run. 'self.callback' will be executed after the request
    has been processed (in the main thread) with the data in 'self.results' and
    an error code in 'self.status'. These two member variables (results and status)
    should be set by the user code in the execute method. If there is an error, the
    member variable 'error' should be set with some error state information.

    Request classes are registered with the enterprise service so they can be invoked
    by name by client applications. 
    """
    lastId = 0

    def __init__(self, callback, errback):
        self.status = 0
        self.error = None
        self.results = None
        self.callback = callback
        self.errback = errback
        self.id = Request.lastId
        Request.lastId = Request.lastId + 1

    def execute(self, connection):
        """Method to be implemented by derived classes. this is run when the
        request is processed. This will be run within a try/except block that
        catched database exceptions.  The results of the query should be stored in
        the member variable 'results'. set self.status to 1 for successful execution.
        """
        print "WARNING: empty Request being run"
        self.status = 0



class GenericRequest(Request):
    """Generic sql execution request.
    """
    def __init__(self, sql, args, callback, errback):
        Request.__init__(self, callback, errback)
        self.sql = sql
        self.args = args

    def execute(self, connection):
        c = connection.cursor()
        if self.args:
            c.execute(self.sql, params=self.args)
        else:
            c.execute(self.sql)
        self.results = c.fetchall()
        c.close()
        #print "Fetchall :", c.fetchall()
        self.status = 1

class AddUserRequest(Request):
    """DbRequest to add a user to the accounts table
    """
    def __init__(self, name, password, callback, errback):
        Request.__init__(self, callback, errback)
        self.name = name
        self.password = password

    def execute(self, connection):
        c = connection.cursor()
        c.execute("insert into accounts (name, passwd, account_id) values ('%s', '%s', 0)" % (self.name, self.password) )
        c.fetchall()
        c.close()
        connection.commit()
        self.status = 1

class PasswordRequest(Request):
    """DbRequest to look up the password for a user in the accounts table.
    """
    def __init__(self, name, callback, errback):
        Request.__init__(self, callback, errback)
        self.name = name

    def execute(self, connection):
        c = connection.cursor()
        c.execute("select passwd from accounts where name = '%s'" % self.name)
        row = c.fetchall()
        if not row:
            # username not found.
            self.status = 0
            return None
        self.results = row[0]
        c.close()
        self.status = 1


