from bingtile import *
import shapefile
import subprocess
import os
import glob
import multiprocessing as mp
import time
from pprint import pp
import sys


def CreateGlobalMapperScript(index, subQKeys, opts):
    script_path = opts.Basepath / f"tilescript_{str(index).rjust(3, '0')}.gms"
    script = open(script_path, 'w')
    script.write('GLOBAL_MAPPER_SCRIPT VERSION=1.00\n')
    script.write('PROMPT_IF_PROJ_UNKNOWN=NO\n')
    script.write('PROMPT_IF_TYPE_UNKNOWN=NO\n')
    for path in opts.DEMInputFiles:
        script.write(
            f'IMPORT FILENAME="{path}" ELEV_UNITS=METERS ELEV_SCALE=1\n')
    script.write('LOAD_PROJECTION PROJ="EPSG:4326"\n')
    for subQKey in subQKeys:
        west, north, east, south = qKeyToBoundingLatLong(subQKey)
        pw, ph = PixelDimensions(east, west, north, south, 256)
        level = len(subQKey)
        fn = opts.Basepath / "Tile" / str(level) / f"dem_{subQKey}.bil"
        args = [
            "EXPORT_ELEVATION", "TYPE=BIL", "USE_UNSIGNED=NO",
            "BYTES_PER_SAMPLE=2", f"SPATIAL_RES={pw},{ph}",
            "FORCE_SQUARE_PIXELS=NO", "ELEV_UNITS=METERS",
            "SAMPLING_METHOD=LAYER", "GEN_PRJ_FILE=YES",
            f"LAT_LON_BOUNDS={west},{south},{east},{north}",
            f"FILENAME='{fn}'\n"
        ]
        # script.write(" ".join(args))
        script.write(
            'EXPORT_ELEVATION TYPE=BIL USE_UNSIGNED=NO BYTES_PER_SAMPLE=2 SPATIAL_RES='
            + str(pw) + ',' + str(ph) +
            ' FORCE_SQUARE_PIXELS=NO ELEV_UNITS=METERS SAMPLING_METHOD=LAYER GEN_PRJ_FILE=YES LAT_LON_BOUNDS='
            + str(west) + ',' + str(south) + ',' + str(east) + ',' +
            str(north) + f' FILENAME="{fn}"\n')
    script.close()


def RunGMScripts(exepath, basepath: Path, threads):
    files = [f for f in basepath.glob('tilescript*.gms')]
    pool = mp.Pool(threads)
    res = []
    for idx, script in enumerate(files):
        res.append('')
        res[idx] = pool.apply_async(runGMScript,
                                    args=(script, exepath),
                                    callback=None)
    pool.close()
    donecount = 0
    while True:
        time.sleep(1)
        dc = 0
        for re in res:
            if re.ready():
                dc += 1
        if dc != donecount:
            print(f'Done {dc} of {len(res)}')
            donecount = dc
        if dc == len(res):
            break
    pool.join()


def RunGMScriptsDetached(exepath, basepath: Path):
    DETACHED_PROCESS = 0x00000008

    files = [f for f in basepath.glob('tilescript*.gms')]

    for file in files:
        args = [exepath, file.as_posix()]
        print("spawning: ", " ".join(args))
        pid = subprocess.Popen(args, creationflags=DETACHED_PROCESS).pid
        # pid = subprocess.Popen([exepath, "longtask.py"],
        #                        creationflags=DETACHED_PROCESS).pid


def runGMScript(file_path, exepath):
    subprocess.run([exepath, file_path.as_posix()])
    return 0


def createGMVisualizationScript(options):
    script = open(options.Basepath / "visualize.gmw", 'w')
    script.write('GLOBAL_MAPPER_SCRIPT VERSION=1.00\n')
    for path in options.DEMInputFiles:
        script.write('IMPORT FILENAME=\"' + path +
                     '" ELEV_UNITS=METERS ELEV_SCALE=1\n')
    coverage_file = options.Basepath / 'qKeyCoverage.shp'
    script.write(
        f'IMPORT FILENAME="{coverage_file}" LABEL_FIELD="name" PROJ="EPSG:4326"\n'
    )


def visualize(exepath, basepath: Path):
    args = [exepath, Path(basepath / 'visualize.gmw').as_posix()]
    subprocess.run(args)


def createCoveragePolyShapefile(qKeys, basepath: Path):
    shape_filename = basepath / 'qKeyCoverage.shp'
    w = shapefile.Writer(shape_filename)
    w.field('name', 'C')
    w.field('paddingtile', 'L')
    for qKey in qKeys:
        west, north, east, south = qKeyToBoundingLatLong(qKey[0])
        w.poly([[[west, north], [east, north], [east, south], [west, south]]])
        w.record(qKey[0], qKey[1])
    w.close()
    writeProjectionFile(shape_filename.with_suffix(".prj"))


def writeProjectionFile(input_filename: Path):
    prj = open(input_filename, 'w')
    proyeccion = 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
    prj.write(proyeccion)


def writeBILHeader(input_filename: Path):
    x = """BYTEORDER      I
LAYOUT         BIL
NROWS          257
NCOLS          257
NBANDS         1
NBITS          16
BANDROWBYTES   514
TOTALROWBYTES  514
BANDGAPBYTES   0
NODATA         -9999
ULXMAP         -123.046875
ULYMAP         36.5978891330702
XDIM           0.00034332275390625
YDIM           0.00027575905673427"""
    input_filename.write_text(x)

    # xyl = bingtile.QuadKeyToTileXY(fullqkey)
    # pxy = bingtile.TileXYToPixelXY(xyl[0], xyl[1])
    # print(pxy)
    # print(xyl)
    # platlon = bingtile.PixelXYToLatLong(pxy[0], pxy[1], xyl[2])
    # yul = platlon[0]
    # xul = platlon[1]
    # pxy = bingtile.TileXYToPixelXY(xyl[0]+1, xyl[1]+1)
    # platlon = bingtile.PixelXYToLatLong(pxy[0], pxy[1], xyl[2])
    # yhep = (yul-platlon[0])/256
    # xwdp = (platlon[1]-xul)/256
    # xul = xul+(xwdp/2)
    # yul = yul-(yhep/2)
    # outfile = open(dst+"dem_"+fullqkey+".hdr", "w")
    # outfile.write("BYTEORDER      I\n")
    # outfile.write("LAYOUT         BIL\n")
    # outfile.write("NROWS          257\n")
    # outfile.write("NCOLS          257\n")
    # outfile.write("NBANDS         1\n")
    # if outsize==66056:
    #     outfile.write("NBITS          8\n")
    #     outfile.write("BANDROWBYTES   257\n")
    #     outfile.write("TOTALROWBYTES  257\n")
    # elif outsize==132105:
    #     outfile.write("NBITS          16\n")
    #     outfile.write("BANDROWBYTES   514\n")
    #     outfile.write("TOTALROWBYTES  514\n")
    # outfile.write("BANDGAPBYTES   0\n")
    # outfile.write("NODATA         -9999\n")
    # outfile.write("SKIPBYTES      7\n")
    # outfile.write("PIXELTYPE      SIGNEDINT\n")
    # outfile.write("ULXMAP         "+str(xul)+"\n")
    # outfile.write("ULYMAP         "+str(yul) + "\n")
    # outfile.write("XDIM           "+str(xwdp)+"\n")
    # outfile.write("YDIM           "+str(yhep)+"\n")
    # outfile.close()


def calculateMaxDiskUsageMB(qKeyCount, options):
    singleQKeyTiles = SubtileCount(options.CGLLevel, options.CGLLevel,
                                   options.MaxLevel)
    singleQKeyDeltas = SubtileCount(options.CGLLevel, options.CGLLevel + 1,
                                    options.MaxLevel)
    totalFileCount = qKeyCount * singleQKeyTiles + qKeyCount * singleQKeyTiles
    totalSize = totalFileCount * 132098 / 1048576 + (qKeyCount * 2 * 100)
    return totalSize
