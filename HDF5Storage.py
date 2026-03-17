import argparse
import pickle
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import h5py
import numpy as np

class HDF5Storage:
    def __init__(self, path: str, chunk_size: int = 6500, buffer_packets: int = 200):
        self.path = Path(path)
        self.chunk_size = chunk_size
        self.buffer_packets = buffer_packets
        self.buffer = []  # List of packets to buffer before writing
        # Ensure file and datasets exist (empty) so we can append safely.
        self._ensure_datasets()
        self._hdf = h5py.File(self.path, 'a')

    def _ensure_datasets(self):
        """Create empty, resizable datasets if they don't exist."""
        with h5py.File(self.path, 'a') as hdf:
            if 'Timestamps' not in hdf:
                hdf.create_dataset(
                    'Timestamps',
                    shape=(0,),
                    maxshape=(None,),
                    dtype='f8',
                    chunks=(self.chunk_size,),
                )
            if 'Scatter' not in hdf:
                hdf.create_dataset(
                    'Scatter',
                    shape=(0, 64, 16),
                    maxshape=(None, 64, 16),
                    dtype='i4',
                    chunks=(self.chunk_size, 64, 16),
                )
            if 'Spectral' not in hdf:
                hdf.create_dataset(
                    'Spectral',
                    shape=(0, 32, 16),
                    maxshape=(None, 32, 16),
                    dtype='i4',
                    chunks=(self.chunk_size, 32, 16),
                )

    def write_packet(self, packet):
        """Buffer one packet for later batch write."""
        self.buffer.append(packet)
        if len(self.buffer) >= self.buffer_packets:
            self._flush()

    def _flush(self):
        """Write all buffered packets to HDF5 in one batch."""
        if not self.buffer:
            return

        # Concatenate all packets
        all_timestamps = np.concatenate([p["timestamps"] for p in self.buffer])
        all_scattering = np.concatenate([p["scattering"] for p in self.buffer])
        all_spectral = np.concatenate([p["spectral"] for p in self.buffer])

        # Write to HDF5
        with h5py.File(self.path, 'a') as hdf:
            ds_timestamps = hdf["Timestamps"]
            ds_scatter = hdf["Scatter"]
            ds_spectral = hdf["Spectral"]

            current_size = ds_timestamps.shape[0]
            new_size = current_size + len(all_timestamps)

            ds_timestamps.resize((new_size,))
            ds_timestamps[current_size:new_size] = all_timestamps

            ds_scatter.resize((new_size, 64, 16))
            ds_scatter[current_size:new_size, :, :] = all_scattering

            ds_spectral.resize((new_size, 32, 16))
            ds_spectral[current_size:new_size, :, :] = all_spectral

        # Clear buffer
        self.buffer.clear()

    def read_by_time_range(self, start, stop):
        """Return a dict of arrays for particles within [start, stop]."""
        with h5py.File(self.path, 'r') as hdf:
            ts = hdf['Timestamps'][:]
            mask = (ts >= start) & (ts <= stop)
            if not mask.any():
                return {'timestamps': np.empty((0,), dtype=ts.dtype),
                        'scattering': np.empty((0, 64, 16), dtype='i4'),
                        'spectral': np.empty((0, 32, 16), dtype='i4')}

            idx = np.nonzero(mask)[0]
            return {
                'timestamps': ts[idx],
                'scattering': hdf['Scatter'][idx],
                'spectral': hdf['Spectral'][idx],
            }

    def read_exact(self, stream, n: int) -> bytes:
        """Read exactly *n* bytes from *stream*, or return empty on EOF."""
        data = b""
        while len(data) < n:
            chunk = stream.read(n - len(data))
            if not chunk:
                return b""
            data += chunk
        return data

    def get_packet_from_stream(self) -> [dict[str, np.array], int]:
        """Read one packet from data_generator, or return empty on EOF.

        Return a tuple (decoded data , raw data length)
        """
        stdin = sys.stdin.buffer

        # Read the 4-byte length prefix
        header = self.read_exact(stdin, 4)
        if not header:
            return b"", 0

        (length,) = struct.unpack(">I", header)

        # Read the payload
        payload = self.read_exact(stdin, length)
        if not payload:
            raise ValueError("Empty payload")

        # Deserialize
        return pickle.loads(payload), len(payload) + 4
    
    def cmd_write(self):
        total_bytes_received = 0
        packets_written = 0

        while True:
            packet, raw_data_length = self.get_packet_from_stream()
            if packet == b"":
                break
            self.write_packet(packet)
            packets_written += 1
            total_bytes_received += raw_data_length

        # Flush any remaining buffered packets
        self._flush()

        print(
            f"Wrote to storage {packets_written} packets "
            f"({total_bytes_received} bytes).",
            file=sys.stderr,
        )

    def cmd_read(self, start_iso: str, stop_iso: str):
        start = datetime.fromisoformat(start_iso).replace(tzinfo=timezone.utc).timestamp()
        stop = datetime.fromisoformat(stop_iso).replace(tzinfo=timezone.utc).timestamp()

        print(f"Reading data between {start_iso} and {stop_iso}")
        t0 = time.monotonic()
        result = self.read_by_time_range(start, stop)
        dt = time.monotonic() - t0

        count = len(result["timestamps"])
        print(f"Found {count} particles.")
        if dt > 0:
            print(f"Read bandwidth {count/dt:.2f} kParticles/s." )
