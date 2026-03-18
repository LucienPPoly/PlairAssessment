---
title: "Plair Technical Challenge Solution"
author: Lucien Poissonnier
date: Feb 17, 2026
---


# Data Storage Challenge Solution

![Python](https://img.shields.io/badge/Python-3.12.7-blue?style=flat-square&logo=python&logoColor=white) ![NumPy](https://img.shields.io/badge/NumPy-2.4.2-4DABCF?style=flat-square&logo=numpy&logoColor=white) ![h5py](https://img.shields.io/badge/h5py-3.12.1-E8A020?style=flat-square)

## Dependencies
This program requires the external librairies [numpy](https://numpy.org/doc/2.4/) and [h5py](https://docs.h5py.org/en/stable/).

### Quick setup script
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install numpy h5py
```

### How to run
```bash
# Write
python3 data_generator.py --pps 150 --max-mb 500 | python3 main_storage.py --storage-file <output file> write

# Read
python3 main_storage.py --storage-file <output file> read --start <starting timestamp> --stop <ending timestamp>
```

## Data format choice
I did some research to find the data format that would best suit the challenge's contraints. I oriented myself toward HDF5 format because it supports matrices, it can orgnanize huge amount of data efficiently and clearly relying on groups and subgroups of data, it can also be queried effitiently as shown in the read_by_time_range() function : while CSV or JSON require the program to scan the entierity of the file, one can use binary masks to retrieve the indexes of the data falling between two timestamps. Other formats like Parquet, SQLite or Zarr wouldn't do because the first two don't handle multi-dimensional arrays, and the later is less mature than HDF5.

## Software architecture choice
The architechure I chose is simple : one Python class (HDF5Storage) hosts the core functions of the reading and writing steps, and a wrapper (my_storage.py) allows for the use of CLI commands and arguments to manipulate this class. This allows for quick reusability across projects.

## Trade-offs
* I used a buffer to reduce the amount of on-disk writing on the HDF5 file, while this improves the performances, it brings a risk of loss in data is the program crashes before the buffer is flushed on the disk.


## What can be improved
* The main point to be improved would be the performances, while I managed to get around 45 kParticles/sec in writing, I feel like there's room for better optimization to be done through more advanced batching strategies or lower-level HDF5 tuning. 

* The read_by_timerange() function loads the entireity of the dataset in memory, which can cause problems if we use large ammount of data. This can be improved with an external time index or use subgroups to divide the data in time periods.
