import glob
import os
import statistics
import subprocess
import sys
import time

GMExePath: str = r'C:\Program Files\GlobalMapper21.0_64bit\global_mapper.exe'
# Run scripts generated in previous file
files = glob.glob("tilescript*.gms")

for file in files:
    # cmd = f"{GMExePath} {file}"
    args = [GMExePath, file]
    print(" ".join(args))
    # os.system(cmd)
    subprocess.run(args)
# sys.exit()

# Monitor tile creation process
tilecount = 4096
deltas = []
previous = 0
while True:
    count = len(glob.glob("Tile/*/*.rw"))
    if previous == 0:
        previous = count
    else:
        delta = count - previous
        deltas.append(delta)
        if len(deltas) > 30:
            deltas.pop(0)
        avg = statistics.mean(deltas)
        left = tilecount - count
        previous = count
        if avg > 0:
            secondsleft = left / avg
        else:
            secondsleft = -1
        print("Done: " + str(count).rjust(7, '0') + " of " + str(tilecount) +
              " Time left: " + f"{secondsleft:.0f}")
        time.sleep(1)
        if count == tilecount:
            break
