from bingtile import ListAllSubQKeys, CoordsToQkeyList
from GMTiles import *
from pyramidGen import createPyramids
from cgl_generate import createCGLs
from packageGen import makePackageFolder
from misc import chunks
from dataclasses import dataclass
import os
import click
import cgl_generate as cglc
from pprint import pprint as pp
from pathlib import Path

SOURCEDEM = "USGS"
LEVEL = 12

# Manifest data that will be written to the manifest.json in package folder.
# Fill title, creator, package_version and release notes.
manifest = {
    "dependencies": [],
    "content_type": "SCENERY",
    "title": f"{SOURCEDEM}-LEVEL{LEVEL}-SAMO-MTS",
    "manufacturer": "",
    "creator": "zcole",
    "package_version": "0.2.1",
    "minimum_game_version": "1.11.6",
    "release_notes": {
        "neutral": {
            "LastUpdate": "Latest release note",
            "OlderHistory": "These can be seen in package manager"
        }
    }
}


@dataclass
# Options for configuring DEM tile and CGL generation
# https://learn.microsoft.com/en-us/bingmaps/articles/bing-maps-tile-system
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
    MaxLevel: int = 14
    # print(MaxLevel)
    CGLLevel: int = 14
    # TODO: the 6->12 spread is making more tiles and more detail?
    # print(CGLLevel)
    # 6 = ~2.5km
    # 10 = ~153m
    # 12 = ~40m
    # 13 = ~20m
    # 14 = ~10m
    # 15 = ~5m
    # 16 = ~2.5m
    # 17 = ~1m
    padding: int = 1
    DEMInputFiles = [
        # r'D:\shows\vast\assets\scenery\terrain_samo_mtls\cgl_conversion_test\usgs_egm08\usgs_egm08.gmc'
        # r'D:\shows\vast\assets\scenery\terrain_samo_mtls\cgl_conversion_test\tiled3_dem_1m_egm08\tiled3_dem_1m.gmc'
        r'D:\shows\vast\assets\scenery\terrain_samo_mtls\cgl_conversion_test\usgs3_egm08\usgs3_egm08.gmc'
    ]
    GMExePath: str = r'C:\Program Files\GlobalMapper21.0_64bit\global_mapper.exe'
    # print(mp.cpu_count())
    GMThreads: int = mp.cpu_count()
    GMThreads: int = 12
    # GMThreads: int = 1
    ProcessingThreads: int = mp.cpu_count()
    # ProcessingThreads: int = 1
    # Basepath: str = os.path.abspath('C:/cgltemp')
    Basepath: Path = Path('C:/cgltemp')

    # Basepath: str = os.path.abspath('./_temp/')
    TargetName: str = f"zcole-dem-samomts-lvl{MaxLevel}"


@dataclass
class LongLat():
    longitude: float = 0
    latitude: float = 0


# UpperLeft and LowerRight coordinates for target area
# If area covers multiple cgls, multiple cgls will be generated.
# longlatUL = LongLat(-119.088604035, 34.191287555)
# longlatLR = LongLat(-118.486488978, 33.989269803)

# longlatUL = LongLat(-118.85185, 34.05264)
# longlatLR = LongLat(-118.65655, 34.02528)

# longlatUL = LongLat(18.60, 70.75)
# longlatLR = LongLat(31.90, 59.20)

# longlatUL = LongLat(-119.14444, 34.16543)
# longlatLR = LongLat(-118.77442, 33.99644)

# nevada and california coordinates
# longlatUL = LongLat(-124.8083, 42.0956)
# longlatLR = LongLat(-114.197, 32.195)

# # 023012
# txy = QuadKeyToTileXY("023012")
# # print(txy)
# pxy = TileXYToPixelXY(txy[0], txy[1])
# ul = PixelXYToLatLong(pxy[0], pxy[1], txy[2])
# # print(ul)
# pxy = TileXYToPixelXY(txy[0] + 1, txy[1] + 1)
# lr = PixelXYToLatLong(pxy[0] - 0, pxy[1] - 0, txy[2])
# # print(lr)
# longlatUL = LongLat(ul[1] - 1, ul[0] + 0.5)
# longlatLR = LongLat(lr[1] + 1, lr[0] - 0.5)

# 32.360, -118.685

if __name__ == '__main__':
    Opts = Options()
    # TopLevelQKeys = CoordsToQkeyList(longlatUL, longlatLR, Opts)
    # here i just want one whole quad key to test
    TopLevelQKeys = [['023012', 0]]
    createCoveragePolyShapefile(TopLevelQKeys, Opts.Basepath)
    createGMVisualizationScript(Opts)
    diskspaceneeded = calculateMaxDiskUsageMB(len(TopLevelQKeys), Opts)
    print(f"Maximum space needed will be around {diskspaceneeded/100:0.1f}GB")
    print("If padding tiles are not \"full\", it will be less")
    print("Showing quadkeys over source data in global mapper")
    print(
        "When padding enabled, outermost tiles don't have to be completely covered"
    )
    print("1/3 of width/height should be enough")
    print("Check if coverage is OK")
    # visualize(Opts.GMExePath, Opts.Basepath)
    # if click.confirm('Everything OK? Continue?', default=True):
    if True:
        for i in range(Opts.CGLLevel, Opts.MaxLevel + 1):
            Path(Opts.Basepath / "Tile" / str(i)).mkdir(parents=True,
                                                        exist_ok=True)
            Path(Opts.Basepath / "Delta" / str(i)).mkdir(parents=True,
                                                         exist_ok=True)
        allSubQKeys = ListAllSubQKeys(TopLevelQKeys, Opts.MaxLevel,
                                      Opts.Basepath)
        # print(allSubQKeys)
        totalSubCount = len(allSubQKeys)
        print(totalSubCount)
        # subsPerChunk = int(totalSubCount / (Opts.GMThreads * 2))
        subsPerChunk = int(totalSubCount / Opts.GMThreads)
        # print(subsPerChunk)
        subQKeyChunks = chunks(allSubQKeys, subsPerChunk)
        y = [x for x in subQKeyChunks]
        print(len(y))
        for index, chunk in enumerate(y):
            CreateGlobalMapperScript(index, chunk, Opts)
        RunGMScriptsDetached(Opts.GMExePath, Opts.Basepath)
        # better stategy is to build tiles out of Global Mapper for each level instead of building pyramid
        # if totalSubCount < Opts.GMThreads:
        #     CreateGlobalMapperScript(0, allSubQKeys, Opts)
        #     RunGMScripts(Opts.GMExePath, Opts.Basepath, Opts.GMThreads)
        # else:
        #     if True:
        #         for index, chunk in enumerate(subQKeyChunks):
        #             CreateGlobalMapperScript(index, chunk, Opts)
        #         RunGMScripts(Opts.GMExePath, Opts.Basepath, Opts.GMThreads)
        # createPyramids(TopLevelQKeys, Options)
        # createCGLs(TopLevelQKeys, Opts.Basepath, Opts.ProcessingThreads)
        # makePackageFolder(TopLevelQKeys, Options, manifest)
        # print("Done!")
        # print("Ready to fly folder " + Opts.TargetName + " is at")
        # print(Opts.Basepath)
        # print("Just copy to Community to check if it works")
