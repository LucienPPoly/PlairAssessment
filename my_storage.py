import argparse
import pickle
import struct
import sys
import time
from datetime import datetime, timezone
from HDF5Storage import HDF5Storage
import numpy as np
import data_generator


def main():
    parser = argparse.ArgumentParser(
        description="Example of data storage system",
    )
    parser.add_argument(
        "--storage-file",
        type=str,
        default=None,
        help="Storage file location (HDF5)",
    )

    sub = parser.add_subparsers(dest="command")

    # -- write --
    p_w = sub.add_parser("write", help="Ingest packets from stdin")

    # -- read --
    p_r = sub.add_parser("read", help="Query by time range")
    p_r.add_argument(
        "--start",
        required=True,
        help="Start timestamp (ISO 8601 format, inclusive)",
    )
    p_r.add_argument(
        "--stop",
        required=True,
        help="Stop timestamp (ISO 8601 format, inclusive)",
    )

    args = parser.parse_args()

    if args.storage_file is None:
        parser.error("--storage-file is required")

    storage = HDF5Storage(args.storage_file)

    if args.command == "write":
        storage.cmd_write()
    elif args.command == "read":
        storage.cmd_read(args.start, args.stop)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
