from twisted.enterprise import requests
from twisted.enterprise import service

class TestRequest(requetss.Request):
    """Generic sql execution request.
    """
    def __init__(self, sql, args, callback, errback):
        requests.Request.__init__(self, callback, errback)
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


def loadRequests(service):
    service.registerRequest("test", TestRequest)
