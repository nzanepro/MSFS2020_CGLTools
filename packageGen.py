import os
import cv2
import json
import numpy as np
from datetime import datetime
from calendar import timegm
import time
from shutil import copyfile
from pathlib import Path


def dt_to_filetime(dt):
    EPOCH_AS_FILETIME = 116444736000000000  # January 1, 1970 as MS file time
    HUNDREDS_OF_NANOSECONDS = 10000000
    return EPOCH_AS_FILETIME + (timegm(dt.timetuple()) *
                                HUNDREDS_OF_NANOSECONDS)


from shutil import rmtree


def makePackageFolder(TopLevelQKeys, opts, manifest):
    foldername = Path(opts.Basepath / opts.TargetName)
    if foldername.exists() and foldername.is_dir():
        rmtree(foldername, ignore_errors=True)
    foldername.mkdir(exist_ok=True, parents=True)
    manifestfile = open(foldername / "manifest.json", 'w')
    manifestfile.write(json.dumps(manifest, indent=4))
    manifestfile.close()
    thumbnail = np.zeros((170, 412, 3), dtype='uint8')
    font = cv2.FONT_HERSHEY_COMPLEX
    cv2.putText(thumbnail, opts.TargetName, (10, 95), font, 1, (255, 255, 255),
                2, cv2.LINE_AA)
    content_info_folder = Path(foldername / "ContentInfo" / opts.TargetName)
    content_info_folder.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(content_info_folder / "Thumbnail.jpg", thumbnail)
    layout = {
        "content": [{
            "path":
            "ContentInfo/" + opts.TargetName + "/Thumbnail.jpg",
            "size":
            os.path.getsize(content_info_folder / "Thumbnail.jpg"),
            "date":
            dt_to_filetime(datetime.fromtimestamp(time.time()))
        }]
    }
    for qKey in TopLevelQKeys:
        if qKey[1] == False:
            key = qKey[0][0:3]
            subkey = qKey[0][3:6]
            cgl_dir = Path(foldername / "CGL" / key)
            cgl_dir.mkdir(exist_ok=True, parents=True)
            fn_from = f"dem_{subkey}.cgl"
            fn_to = f"dem{subkey}.cgl"
            to_path = cgl_dir / fn_to
            copyfile(opts.Basepath / key / fn_from, to_path)
            size = os.path.getsize(to_path)
            date = dt_to_filetime(datetime.fromtimestamp(time.time()))
            layout["content"].append({
                "path":
                to_path.relative_to(foldername).as_posix(),
                "size":
                size,
                "date":
                date
            })
    layoutfile = open(foldername / "layout.json", 'w')
    layoutfile.write(json.dumps(layout, indent=4))
    layoutfile.close()
