import io
from twisted.logger import eventsFromJSONLogFile
from analyze import analyze

for event in eventsFromJSONLogFile(io.open("log.json")):
    analyze(event)
