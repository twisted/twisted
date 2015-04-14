from twisted.logger import Logger

class MyObject(object):
    log = Logger()

    def __init__(self, value):
        self.value = value

    def doSomething(self, something):
        self.log.info(
            "Object with value {log_source.value!r} doing {something}.",
            something=something
        )

MyObject(7).doSomething("a task")
