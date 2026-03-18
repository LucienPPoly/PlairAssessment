#!/usr/bin/env python3
"""
HDF5-based storage backend for the Plair data storage challenge.
 
Stores particle data (timestamps, scattering, spectral arrays) into a
resizable HDF5 file. Incoming packets are buffered in memory and flushed
to disk all at once to maximize writing speed.
 
Datasets layout:
  - Timestamps : (N,)        float64  — POSIX epoch seconds
  - Scatter    : (N, 64, 16) int32    — scattering measurements
  - Spectral   : (N, 32, 16) int32    — spectral measurements
 
Each row (index i) corresponds to one particle.
"""

import pickle
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import h5py
import numpy as np

class HDF5Storage:
    # I ran a few tests to see which values of chunk_size and buffer_size would improve the performances, these are the two I got the best results with
    def __init__(self, path: str, chunk_size: int = 6500, buffer_size: int = 2000): 
        self.path = Path(path)
        self.chunk_size = chunk_size
        self.buffer_size = buffer_size
        self.buffer = []  # List of packets to buffer before writing
        self._hdf = h5py.File(self.path, 'a') # Open the file in append mode (closed within the __exit__ method)
        
        self._ensure_datasets() # Ensure file and datasets exist (empty) so we can append safely.

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._flush()  # Flush any remaining buffered packets
        if self._hdf:
            self._hdf.close() # Close the file if opened
        return False

    def _ensure_datasets(self):
        """Create empty, resizable datasets if they don't exist."""
        if 'Timestamps' not in self._hdf:
            self._hdf.create_dataset(
                'Timestamps',
                shape=(0,),
                maxshape=(None,),
                dtype='f8',
                chunks=(self.chunk_size,),
                compression=('lzf') # LZF compression to reduce data size while keeping a good speed
            )
        if 'Scatter' not in self._hdf:
            self._hdf.create_dataset(
                'Scatter',
                shape=(0, 64, 16),
                maxshape=(None, 64, 16),
                dtype='i4',
                chunks=(self.chunk_size, 64, 16),
                compression=('lzf')
            )
        if 'Spectral' not in self._hdf:
            self._hdf.create_dataset(
                'Spectral',
                shape=(0, 32, 16),
                maxshape=(None, 32, 16),
                dtype='i4',
                chunks=(self.chunk_size, 32, 16),
                compression=('lzf')
            )

    def write_packet(self, packet):
        """Buffer one packet for later batch write."""
        self.buffer.append(packet)
        if len(self.buffer) >= self.buffer_size:
            self._flush()

    def _flush(self):
        """Write all buffered packets to output file at once."""
        if not self.buffer:
            return

        # Concatenate all packets
        all_timestamps = np.concatenate([p["timestamps"] for p in self.buffer])
        all_scattering = np.concatenate([p["scattering"] for p in self.buffer])
        all_spectral = np.concatenate([p["spectral"] for p in self.buffer])

        # Write to output file
        ds_timestamps = self._hdf["Timestamps"]
        ds_scatter = self._hdf["Scatter"]
        ds_spectral = self._hdf["Spectral"]

        # Resize the datasets to store the new packet
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
        
        ts = self._hdf['Timestamps'][:] # Load the timestamps
        mask = (ts >= start) & (ts <= stop) # Mask the timestamps corresponding to the specified timerange
        if not mask.any():
            return {'timestamps': np.empty((0,), dtype=ts.dtype),
                    'scattering': np.empty((0, 64, 16), dtype='i4'),
                    'spectral': np.empty((0, 32, 16), dtype='i4')}

        idx = np.nonzero(mask)[0] # Get all the indexes from the mask
        start_idx = idx[0] # Prefer slicing than fancy indexing since the datas are in chronological order
        end_idx = idx[-1] + 1
        
        return {
            'timestamps': ts[start_idx:end_idx],
            'scattering': self._hdf['Scatter'][start_idx:end_idx],
            'spectral': self._hdf['Spectral'][start_idx:end_idx],
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
        total_particles = 0
        t0 = time.monotonic() # start the timer

        while True: # While no EOF is encoutered, read the data from stdin
            packet, raw_data_length = self.get_packet_from_stream()
            if packet == b"":
                break
            self.write_packet(packet)
            total_particles += len(packet["timestamps"])
            packets_written += 1
            total_bytes_received += raw_data_length

        # Flush any remaining buffered packets
        self._flush()

        dt = time.monotonic() - t0 # end the timer

        print(
            f"Wrote to storage {packets_written} packets "
            f"({total_bytes_received} bytes).",
            file=sys.stderr,
        )
        print(f"Write speed {total_particles / dt:.2f} kParticles/s.")

    def cmd_read(self, start_iso: str, stop_iso: str):
        start = datetime.fromisoformat(start_iso).replace(tzinfo=timezone.utc).timestamp() # Converts the start and stop value as POSIX format
        stop = datetime.fromisoformat(stop_iso).replace(tzinfo=timezone.utc).timestamp()

        print(f"Reading data between {start_iso} and {stop_iso}")
        t0 = time.monotonic() # start the timer
        result = self.read_by_time_range(start, stop) # retrieve the values
        dt = time.monotonic() - t0 # end the timer

        count = len(result["timestamps"])
        print(f"Found {count} particles.")
        if dt > 0:
            print(f"Read bandwidth {count/dt:.2f} kParticles/s.")
