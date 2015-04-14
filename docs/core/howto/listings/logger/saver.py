import io
from twisted.logger import jsonFileLogObserver, Logger

log = Logger(observer=jsonFileLogObserver(io.open("log.json", "a")),
             namespace="saver")

def loggit(values):
    log.info("Some values: {values!r}", values=values)

loggit([1234, 5678])
loggit([9876, 5432])
