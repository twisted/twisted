
def mathFlow(fount, drain):
    (fount.flowTo(Tube(BytesToLines()))
          .flowTo(Tube(LinesToIntegersOrCommands()))
          .flowTo(Tube(CommandsAndIntegersToResultIntegers()))
          .flowTo(Tube(IntegersToLines()))
          .flowTo(Tube(LinesToBytes()))
        .flowTo(drain))
