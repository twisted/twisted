import io
from twisted.logger import eventsFromJSONLogFile
from analyze import analyze

for event in eventsFromJSONLogFile(open("log.json")):
    analyze(event)
