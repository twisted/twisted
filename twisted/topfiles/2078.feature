reactor.spawnProcess now will not emit a PotentialZombieWarning when called
before reactor.run, and there will be no potential for zombie processes in
this case.
