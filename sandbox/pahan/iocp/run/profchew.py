import hotshot.stats, sys

stats = hotshot.stats.load(sys.argv[1])
stats.sort_stats('time', 'calls')
stats.print_stats()
