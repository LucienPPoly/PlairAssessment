---
title: "Plair Technical Challenge Solution"
author: Lucien Poissonnier
date: Mar 18, 2026
---
# Data Storage Challenge Solution

## Dependencies
This program requires the external librairies numpy and h5py

### Quick setup script
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install numpy h5py
```

### How to run
```bash
# Write
python3 data_generator.py --pps 150 --max-mb 500 | python3 my_storage.py --storage-file <output file> write

# Read
python3 my_storage.py --storage-file <output file> read --start <starting timestamp> --stop <ending timestamp>
```

## Data format choice
I did some research to find the data format that would best suit the challenge's constraints. I oriented myself toward HDF5 format because it supports matrices, it can orgnanize huge amount of data efficiently and clearly relying on groups and subgroups of data, it can also be queried effitiently as shown in the read_by_time_range() function : while CSV or JSON require the program to scan the entierity of the file, one can use binary masks to retrieve the indexes of the data falling between two timestamps. Other formats like Parquet, SQLite or Zarr wouldn't do because the first two don't handle multi-dimensional arrays, and the latter is less mature than HDF5.

## Software architecture choice
The architecture I chose is simple: one Python class (HDF5Storage) hosts the core functions of the reading and writing steps, and a wrapper (my_storage.py) allows for the use of CLI commands and arguments to manipulate this class. This allows for quick reusability across projects.

## Trade-offs
* I used a buffer to reduce the amount of on-disk writing on the HDF5 file. While this improves the performance, it brings a risk of loss in data if the program crashes before the buffer is flushed on the disk.


## What can be improved?
* The main point to be improved would be the performances, while I managed to get around 45 kParticles/sec in writing, I feel like there's room for better optimization to be done. Optimization is still a new subject to me so I'll be glad to learn more to improve my skills!

* The read_by_timerange() function loads the entireity of the dataset in memory, which can cause problems if we use large ammount of data. This can be improved with an external time index or use subgroups to divide the data in time periods.
