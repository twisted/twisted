import argparse
import glob
import os.path
import subprocess
import sys



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory')
    parser.add_argument('--extra', action='append', dest='extras', default=[])

    args = parser.parse_args()

    wheel, = glob.glob(os.path.join(args.directory, '*.whl'))
    if len(args.extras) == 0:
        extras = ''
    else:
        extras = '[{}]'.format(','.join(args.extras))
    subprocess.check_call(['pip', 'install', '{}{}'.format(wheel, extras)])



if __name__ == '__main__':
    sys.exit(main())
