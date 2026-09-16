# %%
import glob

import cgl_decompress as cgld
import cgl_generate as cglc

# decompresses a cgl, only for DEMs
# generates also header files so resulting .rw (BIL) files can be loaded in Global Mapper
# cgld.decompress("_testfiles/dem223.cgl", "120223", "_testfiles/dem120223/")
# cgld.decompress("creator-exampledem/CGL/102/dem231.cgl", "102231",
#                 "_testfiles/dem102231/")
# cgld.decompress("_temp/023/dem011.cgl", "023011", "_testfiles/dem023011/")
cgld.decompress(
    "e:/shows/msfs/scenery/_trespassvr-scenery-builds/fsbase-cgl-023011/CGL/023/dem011.cgl",
    "023011", "_testfiles/dem023011/")
# %%
