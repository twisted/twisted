import io

from twisted.logger import Logger, jsonFileLogObserver

log = Logger(observer=jsonFileLogObserver(open("log.json", "a")), namespace="saver")


def loggit(values):
    log.info("Some values: {values!r}", values=values)


loggit([1234, 5678])
loggit([9876, 5432])
