from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from pprint import pprint as pp
from timeit import default_timer

import click

from bingtile import CoordsToQkeyList, ListAllSubQKeys
from cgl_generate import createCGLs
from GMTiles import *
from misc import chunks
from Options import Options
from packageGen import makePackageFolder
from pyramidGen import createPyramids


@contextmanager
def elapsed_timer():
    start = default_timer()
    elapser = lambda: default_timer() - start
    yield lambda: elapser()
    end = default_timer()
    elapser = lambda: end - start


def elapsed_timer_format(secs):
    min = math.floor(secs / 60)
    sec = secs - (min * 60)
    return f"current elapased: {min} min {sec:0.0f} secs"


# Manifest data that will be written to the manifest.json in package folder.
# Fill title, creator, package_version and release notes.
manifest = {
    "dependencies": [],
    "content_type": "SCENERY",
    "title": "developer tool : world elevation 0 + egm2008 ",
    "manufacturer": "",
    "creator": "trespassvr",
    "package_version": "0.1.0",
    "minimum_game_version": "1.11.6",
    "release_notes": {
        "neutral": {
            "LastUpdate": "Latest release note",
            "OlderHistory": "These can be seen in package manager"
        }
    }
}


@dataclass
class LongLat():
    longitude: float = 0
    latitude: float = 0


# UpperLeft and LowerRight coordinates for target area
# If area covers multiple cgls, multiple cgls will be generated.
longlatUL = LongLat(18.60, 70.75)
longlatLR = LongLat(31.90, 59.20)


def doit():
    # TopLevelQKeys = CoordsToQkeyList(longlatUL, longlatLR, Options)
    # TopLevelQKeys = [
    #     # ["02301231012", 0],  # mugu lvl11
    #     # ['023010', 0],
    #     ['023011', 0],
    #     # ['023012', 0],
    #     # ['023013', 0],
    # ]
    bils = Path("_temp/Tile/6").glob("*.bil")
    TopLevelQKeys = [[b.stem[3:], 0] for b in bils]
    # pp(TopLevelQKeys)

    # return

    # createCoveragePolyShapefile(TopLevelQKeys, Options.Basepath)
    # createGMVisualizationScript(Options)
    # diskspaceneeded = calculateMaxDiskUsageMB(len(TopLevelQKeys), Options)
    # print("Maximum space needed will be around " + str(int(diskspaceneeded)) +
    #       " MB")
    # print("If padding tiles are not \"full\", it will be less")
    # print("Showing quadkeys over source data in global mapper")
    # print(
    #     "When padding enabled, outermost tiles don't have to be completely covered"
    # )
    # print("1/3 of width/height should be enough")
    # print("Check if coverage is OK")
    # visualize(Options.GMExePath, Options.Basepath)
    # if not click.confirm('Everything OK? Continue?', default=True):
    #     return
    with elapsed_timer() as elapsed:
        # pp(TopLevelQKeys)
        # allSubQKeys = []
        # for level in range(Options.CGLLevel, Options.MaxLevel + 1):
        #     print(level)
        #     allSubQKeys.extend(
        #         ListAllSubQKeys(TopLevelQKeys, level, Options.Basepath))
        # print(len(allSubQKeys))
        # # print(allSubQKeys)
        # totalSubCount = len(allSubQKeys)
        # subsPerChunk = int(totalSubCount / Options.GMThreads)
        # subQKeyChunks = chunks(allSubQKeys, subsPerChunk)
        # cleanup old global mapper scripts
        # for item in Path(Options.Basepath).glob("*.gms"):
        #     item.unlink()

        # if totalSubCount < Options.GMThreads:
        #     CreateGlobalMapperScript(0, allSubQKeys, Options)
        #     RunGMScripts(Options.GMExePath, Options.Basepath,
        #                  Options.GMThreads)
        # else:
        #     if True:
        #         for index, chunk in enumerate(subQKeyChunks):
        #             CreateGlobalMapperScript(index, chunk, Options)
        #         RunGMScripts(Options.GMExePath, Options.Basepath,
        #                      Options.GMThreads)

        # let's check they are all the same size
        # check_bil_files(TopLevelQKeys)

        # TODO maybe make a backup copy of level 6 at this point
        # print(elapsed_timer_format(elapsed()))
        createPyramids(TopLevelQKeys, Options)
        print(elapsed_timer_format(elapsed()))
        createCGLs(TopLevelQKeys, Options.Basepath, Options.ProcessingThreads)
        makePackageFolder(TopLevelQKeys, Options, manifest)
        print("Done!")
        print("Ready to fly folder " + Options.TargetName + " is at")
        print(Options.Basepath)
        print("Just copy to Community to check if it works")
        print(elapsed_timer_format(elapsed()))
        # for item in Path(Options.Basepath).glob("*.gms"):
        #     item.unlink()


def check_bil_files(TopLevelQKeys):
    size_goal = 132000
    for qKey, _ in TopLevelQKeys:
        glob_pattern = f"dem{qKey}*.bil"
        for item in Path(Options.Basepath).rglob(glob_pattern):
            # item.s
            if item.stat().st_size < size_goal:
                print(item)
                print(item.stat().st_size)
                break


if __name__ == '__main__':
    doit()
