import rasterio.plot
from collections import OrderedDict


def rasterio_as_image(src):
    # Get RGB image
    source_colorinterp = OrderedDict(zip(src.colorinterp, src.indexes))
    colorinterp = rasterio.enums.ColorInterp
    rgb_indexes = [
        source_colorinterp[ci]
        for ci in (colorinterp.red, colorinterp.green, colorinterp.blue)
    ]
    return rasterio.plot.reshape_as_image(src.read(rgb_indexes, masked=True))
