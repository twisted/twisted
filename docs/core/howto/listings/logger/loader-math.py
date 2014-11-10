import io
from twisted.python.logger import eventsFromJSONLogFile

for event in eventsFromJSONLogFile(io.open("log.json")):
    print(sum(event["values"]))
