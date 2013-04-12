
from twisted.tubes.tube import Tube
from twisted.tubes.framing import BytesToLines
from twisted.tubes.framing import LinesToBytes

def mathFlow(fount, drain):
    (fount.flowTo(Tube(BytesToLines()))
          .flowTo(Tube(LinesToIntegersOrCommands()))
          .flowTo(Tube(CommandsAndIntegersToResultIntegers()))
          .flowTo(Tube(IntegersToLines()))
          .flowTo(Tube(LinesToBytes()))
        .flowTo(drain))
