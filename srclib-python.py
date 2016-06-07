import argparse
import os
import sys

from grapher.scan import scan
from grapher.graph import graph

def main() -> None:
    parser = argparse.ArgumentParser(description="")
    subparsers = parser.add_subparsers(help="", dest="subcmd")

    scanparser = subparsers.add_parser("scan", help="")
    depresolveparser = subparsers.add_parser("depresolve", help="")
    graphparser = subparsers.add_parser("graph", help="")
    graphparser.add_argument('--verbose', help='verbose', action='store_true', default=True)
    graphparser.add_argument('--debug', help='debug', action='store_true', default=False)
    graphparser.add_argument('--quiet', help='quiet', action='store_true', default=False)
    graphparser.add_argument('--unit-file', help="debugging purposes", default=None)


    args = parser.parse_args()
    if args.subcmd == "scan":
        scan(os.getcwd())
    elif args.subcmd == "depresolve":
        print('[]', end="")
    elif args.subcmd == "graph":
        if args.unit_file is not None:
            with open(args.unit_file) as f:
                graph(args, f)
        else:
            graph(args, sys.stdin)

if __name__ == '__main__':
    main()
