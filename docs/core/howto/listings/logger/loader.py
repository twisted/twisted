import sys
import io
from twisted.logger import (
    eventsFromJSONLogFile, textFileLogObserver
)

output = textFileLogObserver(sys.stdout)

for event in eventsFromJSONLogFile(io.open("log.json")):
    output(event)
