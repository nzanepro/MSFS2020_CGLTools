import os
from dataclasses import dataclass

from GMTiles import mp, os


@dataclass
# Options for configuring DEM tile and CGL generation
# CGLLevel: Bing maps tile level that will be the lowest resolution
#           in generated CGLs. Default 6. Don't change.
# MaxLevel: Highest Bing maps tile level used when generating tiles,
#           also DEM tile cutting level. Default 12. Don't change.
# Padding: If enabled (=1), generates extra tiles around target area
#          to minimize edge errors. Default 1.
# DEMInputFiles: List of source elevation data files, #! ELEVATION MUST BE RELATIVE TO EGM2008
#                can be any format Global Mapper supports.
# GMExePath: Path to Global Mapper executable.
# GMThreads: How many GM instances to run in parallel
#            to speed up processing.
#            Change based on cpu cores and available memory.
#            Some source material can use gigabytes of memory,
#            while other can use just hundreds of megabytes.
# ProcessingThreads: Laplacian pyramid and GCL compression
#                    parallelization. Default computer thread count.
# BasePath: Path to folder where generated files will go.
#           Default './_temp/' (current_directory/_temp).
# TargetName: Package name for the project.
class Options():
    CGLLevel: int = 6
    MaxLevel: int = 8
    padding: int = 1
    DEMInputFiles = [
        r'D:\shows\vast\assets\scenery\terrain_samo_mtls\cgl_conversion_test\usgs3_egm08\usgs3_egm08.gmc'
    ]
    GMExePath: str = r'C:\Program Files\GlobalMapper21.0_64bit\global_mapper.exe'
    GMThreads: int = mp.cpu_count()
    # GMThreads: int = 10
    ProcessingThreads: int = mp.cpu_count()
    Basepath: str = os.path.abspath('./_temp/')
    TargetName: str = "trespassvr-dev-flat-earth"
    MultiThreadPyramids: bool = False
