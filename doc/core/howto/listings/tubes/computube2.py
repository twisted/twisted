
from twisted.tubes.tube import Tube
from twisted.tubes.framing import bytesToLines, linesToBytes

def mathFlow(fount, drain):
    (fount.flowTo(Tube(bytesToLines()))
          .flowTo(Tube(LinesToIntegersOrCommands()))
          .flowTo(Tube(CommandsAndIntegersToResultIntegers()))
          .flowTo(Tube(IntegersToLines()))
          .flowTo(Tube(linesToBytes()))
        .flowTo(drain))
