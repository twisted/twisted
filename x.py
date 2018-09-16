import argparse
import glob
import os.path
import shutil
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory')

    args = parser.parse_args()

    wheel, = glob.glob(os.path.join(args.directory, '*.whl'))

    shutil.move(wheel, os.path.join(args.directory, 'twisted.whl'))


if __name__ == '__main__':
    sys.exit(main())
