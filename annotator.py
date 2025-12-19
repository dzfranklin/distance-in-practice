import matplotlib

matplotlib.use("qt5agg")

import rasterio
import rasterio.plot
import matplotlib.pyplot as plt
from collections import OrderedDict
import geojson
import json
import sys
import re
import os


class PointAnnotator:
    def __init__(self, ax, meters_per_pixel=None):
        self.ax = ax
        self.segments = []
        self.current_segment = []
        self.markers = []
        self.fig = ax.figure

        self.colors = [
            "purple",
            "red",
            "blue",
            "green",
            "orange",
            "cyan",
            "magenta",
            "yellow",
        ]
        self.current_color_index = 0

        # Store initial view for zoom calculation
        self.initial_xlim = None
        self.initial_ylim = None
        self.zoom_level = 1.0
        self.meters_per_pixel = meters_per_pixel

        # Disable default matplotlib key bindings
        self.fig.canvas.mpl_disconnect(self.fig.canvas.manager.key_press_handler_id)

        self.cid_click = self.fig.canvas.mpl_connect(
            "button_press_event", self.on_click
        )
        self.cid_key = self.fig.canvas.mpl_connect("key_press_event", self.on_key)

    def on_click(self, event):
        if event.inaxes != self.ax:
            return

        if event.button == 1:  # Left click - add point
            self.add_point(event.xdata, event.ydata)
        elif event.button == 3:  # Right click - remove last point
            self.remove_last_point()

    def on_key(self, event):
        if event.key in ["z", "Z"]:  # Undo with 'z'
            self.remove_last_point()
        elif event.key in ["enter", "return"]:  # Finish with Enter
            self.complete_segment()
            plt.close(self.fig)
        elif event.key == " ":
            self.complete_segment()
        elif event.key in ["+", "="]:  # Zoom in
            self.zoom(1.2)
        elif event.key == "-":  # Zoom out
            self.zoom(0.8)
        elif event.key == "w":  # Pan up
            self.pan(0, 0.1)
        elif event.key == "s":  # Pan down
            self.pan(0, -0.1)
        elif event.key == "a":  # Pan left
            self.pan(-0.1, 0)
        elif event.key == "d":  # Pan right
            self.pan(0.1, 0)
        elif event.key == "h":  # Home/reset view
            self.ax.autoscale()
            self.initial_xlim = self.ax.get_xlim()
            self.initial_ylim = self.ax.get_ylim()
            self.zoom_level = 1.0
            self.update_title()
            self.fig.canvas.draw()

    def zoom(self, factor):
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        xmid = (xlim[0] + xlim[1]) / 2
        ymid = (ylim[0] + ylim[1]) / 2
        xrange = (xlim[1] - xlim[0]) / factor
        yrange = (ylim[1] - ylim[0]) / factor
        self.ax.set_xlim(xmid - xrange / 2, xmid + xrange / 2)
        self.ax.set_ylim(ymid - yrange / 2, ymid + yrange / 2)
        self.update_zoom_level()
        self.fig.canvas.draw()

    def pan(self, dx_frac, dy_frac):
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        xrange = xlim[1] - xlim[0]
        yrange = ylim[1] - ylim[0]
        self.ax.set_xlim(xlim[0] + dx_frac * xrange, xlim[1] + dx_frac * xrange)
        self.ax.set_ylim(ylim[0] + dy_frac * yrange, ylim[1] + dy_frac * yrange)
        self.fig.canvas.draw()

    def update_zoom_level(self):
        if self.initial_xlim is None or self.initial_ylim is None:
            return
        current_xlim = self.ax.get_xlim()
        current_ylim = self.ax.get_ylim()
        current_xrange = current_xlim[1] - current_xlim[0]
        current_yrange = current_ylim[1] - current_ylim[0]
        initial_xrange = self.initial_xlim[1] - self.initial_xlim[0]
        initial_yrange = self.initial_ylim[1] - self.initial_ylim[0]
        # Average of x and y zoom
        self.zoom_level = (
            (initial_xrange / current_xrange) + (initial_yrange / current_yrange)
        ) / 2
        self.update_title()

    def update_title(self):
        title_parts = []
        if self.meters_per_pixel is not None:
            title_parts.append(f"{self.meters_per_pixel:.2f}m/px")
        title_parts.append(f"Zoom: {self.zoom_level:.1f}x")
        title_parts.append(
            "Click: add | z: undo | +/-: zoom | wasd: pan | space: complete segment | h: reset | Enter: finish"
        )
        self.ax.set_title(" | ".join(title_parts))

    def add_point(self, x, y):
        x = round(x)
        y = round(y)
        self.current_segment.append([x, y])
        (marker,) = self.ax.plot(
            x,
            y,
            "+",
            markersize=8,
            markeredgewidth=1,
            color=self.colors[self.current_color_index],
        )
        self.markers.append(marker)
        self.fig.canvas.draw()

    def complete_segment(self):
        if self.current_segment:
            self.segments.append(self.current_segment)
            self.current_segment = []
            # Cycle to next color
            self.current_color_index = (self.current_color_index + 1) % len(self.colors)

    def remove_last_point(self):
        if self.current_segment:
            self.current_segment.pop()
            marker = self.markers.pop()
            marker.remove()
            self.fig.canvas.draw()

    def annotate(self):
        # Initialize zoom tracking
        self.initial_xlim = self.ax.get_xlim()
        self.initial_ylim = self.ax.get_ylim()
        self.update_title()
        plt.show()
        return geojson.Feature(None, geojson.MultiLineString(self.segments))


def annotate_image(image_path, geojson_path=None):
    # Load existing GeoJSON if it exists
    existing_segments = []
    if geojson_path and os.path.exists(geojson_path):
        try:
            with open(geojson_path, "r") as f:
                existing_feature = geojson.load(f)
                if existing_feature.get("geometry", {}).get("type") == "MultiLineString":
                    existing_segments = existing_feature["geometry"]["coordinates"]
                    print(f"Loaded {len(existing_segments)} existing segments from {geojson_path}")
        except Exception as e:
            print(f"Warning: Could not load existing GeoJSON: {e}")

    with rasterio.open(image_path) as src:
        # From rasterio.plot.show
        source_colorinterp = OrderedDict(zip(src.colorinterp, src.indexes))
        colorinterp = rasterio.enums.ColorInterp
        # Gather the indexes of the RGB channels in that order
        rgb_indexes = [
            source_colorinterp[ci]
            for ci in (colorinterp.red, colorinterp.green, colorinterp.blue)
        ]
        im = rasterio.plot.reshape_as_image(src.read(rgb_indexes, masked=True))

        _fig, ax = plt.subplots(figsize=(11, 9))
        ax.imshow(im, extent=rasterio.plot.plotting_extent(src))

        # Plot existing segments
        colors = ["pink", "red", "green", "orange", "cyan", "magenta", "yellow"]
        for idx, segment in enumerate(existing_segments):
            xs = [point[0] for point in segment]
            ys = [point[1] for point in segment]
            ax.plot(
                xs,
                ys,
                "o-",
                color=colors[idx % len(colors)],
                markersize=3,
                markeredgewidth=1,
                alpha=0.8,
            )

        # Get meters per pixel from the transform
        # src.transform[0] is the pixel width in the CRS units
        meters_per_pixel = abs(src.transform[0])

        annotator = PointAnnotator(ax, meters_per_pixel=meters_per_pixel)
        # Set the color index to continue from where we left off
        annotator.current_color_index = len(existing_segments) % len(colors)

        new_feature = annotator.annotate()

        # Combine existing and new segments
        all_segments = existing_segments + new_feature["geometry"]["coordinates"]
        return geojson.Feature(None, geojson.MultiLineString(all_segments))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: <map_image.tif>")
        sys.exit(1)
    input_file = sys.argv[1]
    output_file = re.sub(r"\.tif+$", ".geojson", input_file)

    feature = annotate_image(input_file, geojson_path=output_file)
    feature_json = json.dumps(feature, sort_keys=True)
    print(f"Saving {output_file}: {feature_json}")
    with open(output_file, "w") as f:
        f.write(feature_json)
