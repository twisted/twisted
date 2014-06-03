import io
from twisted.python.logger import eventsFromJSONLogFile
from analyze import analyze

for event in eventsFromJSONLogFile(io.open("log.json")):
    analyze(event)
