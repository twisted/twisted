class MyExc(Exception):
    "A sample exception."

try:
    x = 1 + 3
    raise MyExc("I can't go on!")
    x = x + 1
    print x
except MyExc, me:
    print 'error (',me,').  x was:', x
except:
    print 'fatal error! abort!'
