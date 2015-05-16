from twisted.logger import Logger

class AdHoc(object):
    log = Logger(namespace="ad_hoc")

    def __init__(self, a, b):
        self.a = a
        self.b = b

    def logMessage(self):
        self.log.info("message from {log_source} "
                      "where a is {log_source.a} and b is {log_source.b}")
