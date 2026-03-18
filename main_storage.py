#!/usr/bin/env python3
"""
CLI entry point for the HDF5 storage backend.
 
Wraps HDF5Storage with an argparse interface so it can be used directly
from the command line, either to ingest a data stream or to query stored
particles by time range.
 
Usage:
    # Write packets streamed from data_generator.py
    python data_generator.py --pps 150 --max-mb 500 | python my_storage.py --storage-file output.h5 write
 
    # Read particles between two ISO 8601 timestamps
    python my_storage.py --storage-file output.h5 read --start "2026-02-17T15:32:36" --stop  "2026-02-17T15:32:37"
"""

import argparse
import sys
from HDF5Storage import HDF5Storage


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

    with HDF5Storage(args.storage_file) as storage:
        if args.command == "write":
            storage.cmd_write()
        elif args.command == "read":
            storage.cmd_read(args.start, args.stop)
        else:
            parser.print_help()
            sys.exit(1)

if __name__ == "__main__":
    main()
