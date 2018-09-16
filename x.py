import argparse
import glob
import os.path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory')
    parser.add_argument('--extra', action='append', metavar='extras')

    args = parser.parse_args()

    wheel, = glob.glob(os.path.join(args.directory, '*.whl'))
    subprocess.check_call(['pip', 'install', '{}[{}]'.format(wheel, ','.join(args.extras))])

    shutil.move(wheel, os.path.join(args.directory, 'twisted.whl'))


if __name__ == '__main__':
    sys.exit(main())
