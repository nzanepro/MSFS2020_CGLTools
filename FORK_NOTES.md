# Fork Notes

This fork preserves three divergent local experiments as of 2026-09-16, branched from
upstream commit `4ff92cf` (2021-01-13). Each experiment lives on its own branch, and
all three (plus `main`) now carry real pytest coverage added on top of the upstream
code:

- `variant/plain` — the cleanest and soundest of the three experiments. Full test
  suite passes with no bugs found.
- `variant/try3` — near-identical to `main`, but its test suite exposed a real,
  pre-existing, cross-branch bug in `cgl_generate.createBlobMT`'s unshared
  `compressedreturns` dict.
- `variant/mod` — the most ambitious of the three API-wise, but currently has 4
  independently-reproduced real bugs (a tile-layout key-extraction off-by-one that
  corrupts the CGL layout table, a missing directory-creation call, a commented-out
  base-tile write that makes pyramid levels below the first silently produce nothing,
  and four per-quadrant delta writes that all clobber the same filename). It is
  non-functional for real CGL generation until those are fixed.

Ongoing development has since moved away from this Global-Mapper-driven pipeline
toward a pure-Python approach (quadkey math and CGL packing ported elsewhere, with
raster reprojection via `rasterio`/GDAL instead of shelling out to Global Mapper).
This repository is being kept as a working historical snapshot and reference rather
than actively developed further.
