"""Test program for processes."""

import sys, os

test_file_match = "process_test.log.*"
test_file = "process_test.log.%d" % os.getpid()

def main():
    f = open(test_file, 'wb')
    
    # stage 1
    bytes = sys.stdin.read(4)
    f.write("one: %r\n" % bytes)
    # stage 2
    sys.stdout.write(bytes)
    sys.stdout.flush()
    os.close(sys.stdout.fileno())
    
    # and a one, and a two, and a...
    bytes = sys.stdin.read(4)
    f.write("two: %r\n" % bytes)
    
    # stage 3
    sys.stderr.write(bytes)
    sys.stderr.flush()
    os.close(sys.stderr.fileno())
    
    # stage 4
    bytes = sys.stdin.read(4)
    f.write("three: %r\n" % bytes)

    # exit with status code 23
    sys.exit(23)


if __name__ == '__main__':
    main()
