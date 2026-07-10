# -*- coding: utf-8 -*-
"""Script to plot particle and vFish positions
"""
__author__ = "Doug Jackson, QEDA Consulting, LLC"
__email__ = "doug@qedaconsulting.com"
import os
import numpy as np
import pandas as pd
import hvplot.pandas
import holoviews as hv
hv.extension("bokeh")
import geopandas
import panel as pn
import xarray as xr
from datetime import datetime as dt
import logging

workingDir = os.path.dirname(os.path.realpath(__file__))

# Hide vFish that have exited
exitChan = 441

if __name__=="__main__":
    import argparse

    # Read in command line arguments
    parser = argparse.ArgumentParser(description="Script to plot particle and vFish positions.")
    parser.add_argument("--animatePlot", action="store_true", dest="animatePlot", required=False)
    parser.add_argument("--pauseInterval_ms", action="store", dest="pauseInterval_ms", required=False)
    parser.add_argument("--animationStep", action="store", dest="animationStep", required=False)
    parser.add_argument("--animFile1", action="store", dest="animFile1", required=True)
    parser.add_argument("--animFile2", action="store", dest="animFile2", required=False)
    parser.add_argument("--fluxFile1", action="store", dest="fluxFile1", required=False)
    parser.add_argument("--fluxFile2", action="store", dest="fluxFile2", required=False)
    parser.add_argument("--shapeFile", action="store", dest="shapeFile", required=False)
    parser.add_argument("--titleFont", action="store", dest="titleFont", required=False)
    parser.add_argument("--figWidth", action="store", dest="figWidth", required=False)
    parser.add_argument("--figHeight", action="store", dest="figHeight", required=False)
    args = parser.parse_args()

    if args.animatePlot:
        animatePlot = True
        animFile1 = args.animFile1
        animFile2 = None
        fluxFile1 = None
        fluxFile2 = None
    else:
        animatePlot = False
        animFile1= args.animFile1
        animFile2 = args.animFile2
        fluxFile1 = args.fluxFile1
        fluxFile2 = args.fluxFile2

    if args.pauseInterval_ms is not None:
        pauseInterval_ms = int(args.pauseInterval_ms)
    else:
        pauseInterval_ms = 50

    if args.animationStep is not None:
        animationStep = int(args.animationStep)
    else:
        animationStep = 1

    if args.shapeFile is not None:
        DSM2flowlineShapefile = args.shapeFile
    else:
        DSM2flowlineShapefile = os.path.join(workingDir, "shapefile", "i12_DSM2_Model_VSDG1_Channels_Centerlines_Straightlines.shp")
    
    if args.titleFont is not None:
        titleFont = int(args.titleFont)
    else:
        titleFont = 10

    if args.figWidth is not None:
        figWidth = int(args.figWidth)
    else:
        figWidth = 800
    
    if args.figHeight is not None:
        figHeight = int(args.figHeight)
    else:
        figHeight = 600
    
####################################################################################################
# Functions
####################################################################################################
def getChans():
    """Obtain the channel coordinates"""
    DSM2chans = geopandas.read_file(DSM2flowlineShapefile).to_crs(epsg=3857)
    chanList = []
    upNodeXlist = []
    upNodeYlist = []
    downNodeXlist = []
    downNodeYlist = []
    for r in DSM2chans.iterrows():
        chan = r[1]
        upNode = chan.geometry.interpolate(1, normalized=True)
        downNode = chan.geometry.interpolate(0, normalized=True)
        
        chanList.append(chan.id)
        upNodeXlist.append(upNode.coords.xy[0][0])
        upNodeYlist.append(upNode.coords.xy[1][0])
        downNodeXlist.append(downNode.coords.xy[0][0])
        downNodeYlist.append(downNode.coords.xy[1][0])
    chans = pd.DataFrame({"extChannel":chanList, "upNodeX":upNodeXlist, "upNodeY":upNodeYlist,
                          "downNodeX":downNodeXlist, "downNodeY":downNodeYlist})

    b = DSM2chans.to_crs(epsg=3857).geometry.bounds
    extents = (b.minx.min(), b.miny.min(), b.maxx.max(), b.maxy.max())
    
    return chans, extents

def createAnimDF(animFile):
    """Create data frame of animation outputs

    Keyword arguments:
    animFile (str) -- full path to the animation output file
    """
    print(f"Processing animation file: {animFile}")

    ds = xr.open_dataset(animFile)
    anim = ds["anim"].to_pandas().reset_index()
    anim.columns = ["particleNum", "extChannel", "normXdist"]

    chans, extents = getChans()

    # Merge coordinates with records
    anim = pd.merge(anim, chans, how="left", on="extChannel")

    # Load modelDate and modelTime
    modelDate = ds["modelDate"].to_pandas().reset_index()
    modelTime = ds["modelTime"].to_pandas().reset_index()
    
    modelDate.columns = ["timestep", "modelDate"]
    modelTime.columns = ["timestep", "modelTime"]

    modelDate = [m.decode("utf8") for m in modelDate["modelDate"]]
    modelTime = np.array([m.decode("utf8") for m in modelTime["modelTime"]])
    modelTime[np.where(modelTime=="2400")] = "2359"

    modelDatetime = [dt.strptime(f"{d} {t}", "%d%b%Y %H%M") for (d, t) in zip(modelDate, modelTime)]
    datetimeIndex = list(np.arange(0, len(modelDatetime)))
    numRecords = len(modelDatetime)

    # Repeat modelDatetime
    numParticles = len(anim["particleNum"].unique())
    anim["modelDatetime"] = np.repeat(modelDatetime, numParticles)
    anim["datetimeIndex"] = np.repeat(datetimeIndex, numParticles)

    # Calculate interpolated location
    anim["easting"] = anim["upNodeX"] + (anim["normXdist"]/100)*(anim["downNodeX"] - anim["upNodeX"])
    anim["northing"] = anim["upNodeY"] + (anim["normXdist"]/100)*(anim["downNodeY"] - anim["upNodeY"])

    # Hide vFish that have exited
    p_type = ds["particle_type"].item().decode("utf8")
    print(f"particle type: {p_type}")
    if (p_type.upper() == "SALMON_PARTICLE"):
        anim = anim.loc[anim["extChannel"]!=exitChan]

    ds.close()

    print(f"PTM animation file has {numRecords} records")
    print(f"Animation start at {modelDatetime[0]}")
    print(f"Animation ends at {modelDatetime[-1]}")
    print(f"There are {numParticles} particles in this animation")
    
    return anim, extents, numRecords

def createFluxDF(fluxFile):
    """Create data frame of flux outputs

    Keyword arguments:
    fluxFile (str) -- full path to the flux output file
    """
    print(f"Processing flux file: {fluxFile}")

    ds = xr.open_dataset(fluxFile)

    nodeFlux = ds["nodeFlux"].to_pandas()
    nodeFlux.columns = [c.decode("utf8") for c in nodeFlux.columns]
    nodeFlux.index = [i.decode("utf8") for i in nodeFlux.index]
    
    nodes = nodeFlux.columns
    nodeFlux["datetime"] = [dt.strptime(d, "%m/%d/%Y %H:%M:%S") for d in nodeFlux.index]
    
    groupFlux = ds["groupFlux"].to_pandas()
    groupFlux.columns = [c.decode("utf8") for c in groupFlux.columns]
    groupFlux.index = [i.decode("utf8") for i in groupFlux.index]
    
    groups = groupFlux.columns
    groupFlux["datetime"] = [dt.strptime(d, "%m/%d/%Y %H:%M:%S") for d in groupFlux.index]
    
    ds.close()

    flux = pd.merge(nodeFlux, groupFlux, on="datetime", how="outer")
    flux["datetime"] = pd.to_datetime(flux["datetime"])

    return flux

def getDatetime1(value):
    try:
        valDatetime = dt.strptime(str(anim1[anim1["datetimeIndex"]==value]["modelDatetime"].values[0])[:26], "%Y-%m-%dT%H:%M:%S.%f")
        valStr = dt.strftime(valDatetime, "%Y-%m-%d, %H:%M")
        return valStr
    except:
        return anim1[anim1["datetimeIndex"]==value]["modelDatetime"].values[0]

def getDatetime2(value):
    try:
        valDatetime = dt.strptime(str(anim2[anim2["datetimeIndex"]==value]["modelDatetime"].values[0])[:26], "%Y-%m-%dT%H:%M:%S.%f")
        valStr = dt.strftime(valDatetime, "%Y-%m-%d, %H:%M")
        return valStr
    except:
        return anim2[anim2["datetimeIndex"]==value]["modelDatetime"].values[0]

####################################################################################################
# Run
####################################################################################################
logging.basicConfig(level=logging.ERROR)

print("="*100)
print(f"DSM2 flowline shapefile: {DSM2flowlineShapefile}")

print("="*100)
anim1, extents1, numRecords1 = createAnimDF(animFile1)
if animFile2 is not None:
    print("-"*100)
    anim2, extents2, numRecords2 = createAnimDF(animFile2)
else:
    numRecords2 = 0
print("="*100)

fluxLocs = set()
if fluxFile1 is not None:
    flux1 = createFluxDF(fluxFile1)
    thisLocs = list(flux1.columns)
    thisLocs.remove("datetime")
    fluxLocs = fluxLocs | set(thisLocs)

    # Create an array of flux1 datetimes to be used for looking up the closest entry for each animation modelDatetime
    flux1datetime = np.array(flux1["datetime"])

if fluxFile2 is not None:
    flux2 = createFluxDF(fluxFile2)
    thisLocs = list(flux2.columns)
    thisLocs.remove("datetime")
    fluxLocs = fluxLocs | set(thisLocs)

# Use whichever flux datetime array is available for closest-match lookups
if fluxFile1 is not None:
    _flux_datetime = flux1datetime
elif fluxFile2 is not None:
    _flux_datetime = np.array(flux2["datetime"])
else:
    _flux_datetime = None
fluxLocs = list(fluxLocs)
fluxLocs.sort()

if animatePlot:
    # Apply responsive defaults to all HoloViews elements before any plot is created.
    # This prevents hvplot from injecting its default fixed width/height, which would
    # conflict with responsive=True and trigger Bokeh's sizing_mode warning.
    hv.opts.defaults(
        hv.opts.Scatter(responsive=True, min_height=figHeight),
        hv.opts.Segments(responsive=True, min_height=figHeight),
        hv.opts.Tiles(responsive=True, min_height=figHeight),
    )

    # Background tile map (EPSG:3857 matches the particle data projection)
    plotMap = hv.element.tiles.CartoLight()

    chans, extents = getChans()
    chanPlot = hv.Segments(chans, kdims=["upNodeX", "upNodeY", "downNodeX", "downNodeY"]).opts(color="orange", line_width=0.5)

    datetimePlayer = pn.widgets.Player(value=0, start=0, end=(np.max([numRecords1, numRecords2])-1), visible_buttons=["play", "pause"], 
                                       name="Animation controls", loop_policy="loop", step=animationStep, interval=pauseInterval_ms, align="center", 
                                       show_loop_controls=False, show_value=True)
    anim1_df = anim1  # preserve DataFrame reference before binding

    def get_clock_str(timestep):
        try:
            val = anim1_df[anim1_df["datetimeIndex"] == timestep]["modelDatetime"].values[0]
            valDatetime = dt.strptime(str(val)[:26], "%Y-%m-%dT%H:%M:%S.%f")
            return f"## {dt.strftime(valDatetime, '%Y-%m-%d  %H:%M')}"
        except:
            return str(anim1_df[anim1_df["datetimeIndex"] == timestep]["modelDatetime"].values[0])

    clockPane = pn.pane.Markdown(pn.bind(get_clock_str, timestep=datetimePlayer), align="center")

    def make_scatter(timestep):
        frame = anim1_df[anim1_df["datetimeIndex"] == timestep]
        # Pass responsive=True directly to hvplot so it never sets fixed width/height
        return frame.hvplot(x="easting", y="northing", kind="scatter",
                            xlabel="", ylabel="", xticks=0, yticks=0,
                            responsive=True, min_height=figHeight).opts(
                                title=animFile1,
                                fontsize={"title": titleFont},
                                xlim=(extents1[0], extents1[2]),
                                ylim=(extents1[1], extents1[3]))

    scatter_dmap = hv.DynamicMap(pn.bind(make_scatter, timestep=datetimePlayer))
    scatter_dmap.cache_size = 1  # discard old frames immediately to prevent memory growth

    # data_aspect=1 enforces equal x/y scaling (no distortion) while remaining responsive.
    # aspect="equal" cannot be used with responsive mode; data_aspect=1 is the Bokeh equivalent.
    def set_grid_style(plot, element):
        p = plot.handles["plot"]
        p.xgrid.grid_line_width = 2
        p.ygrid.grid_line_width = 2
        p.xgrid.grid_line_color = "gray"
        p.ygrid.grid_line_color = "gray"
        p.xgrid.grid_line_alpha = 0.6
        p.ygrid.grid_line_alpha = 0.6

    combined = (plotMap * chanPlot * scatter_dmap).opts(
        data_aspect=1,
        show_grid=True,
        hooks=[set_grid_style],
    )
    animPane = pn.Column(
        datetimePlayer,
        clockPane,
        pn.panel(combined, sizing_mode="stretch_both"),
        sizing_mode="stretch_both"
    )

    def _on_session_destroyed(session_context):
        import threading
        def _exit():
            import time
            time.sleep(0.01)
            os._exit(0)
        threading.Thread(target=_exit, daemon=True).start()

    pn.state.on_session_destroyed(_on_session_destroyed)
    server = animPane.show()

else:
    # Tiles always in pseudo mercator epsg=3857
    plotMap = hv.element.tiles.CartoLight().opts(responsive=True, min_height=200)
    plotMap.extents = extents1

    pn.config.throttled = True

    datetimeIndexSlider = pn.widgets.IntSlider(value=0, start=0, end=(np.max([numRecords1, numRecords2])-1), name="datetime index")

    # Spatial plots — use pn.bind + hv.DynamicMap so the slider is never auto-embedded
    def make_p1(timestep):
        frame = anim1[anim1["datetimeIndex"] == timestep].dropna(subset=["easting", "northing"])
        return (plotMap * frame.hvplot(x="easting", y="northing", kind="scatter",
                                       responsive=True, min_height=200))\
            .opts(title=animFile1, fontsize={"title": titleFont},
                  data_aspect=1,
                  xlim=(extents1[0], extents1[2]),
                  ylim=(extents1[1], extents1[3]))

    dmap_p1 = hv.DynamicMap(pn.bind(make_p1, timestep=datetimeIndexSlider))
    dmap_p1.cache_size = 1
    col1 = pn.Column(
        pn.panel(pn.bind(getDatetime1, value=datetimeIndexSlider), align="center"),
        pn.panel(dmap_p1, sizing_mode="stretch_both"),
        sizing_mode="stretch_both"
    )

    col2 = pn.Column()
    if animFile2 is not None:
        def make_p2(timestep):
            frame = anim2[anim2["datetimeIndex"] == timestep].dropna(subset=["easting", "northing"])
            return (plotMap * frame.hvplot(x="easting", y="northing", kind="scatter",
                                           responsive=True, min_height=200))\
                .opts(title=animFile2, fontsize={"title": titleFont},
                      data_aspect=1,
                      xlim=(extents2[0], extents2[2]),
                      ylim=(extents2[1], extents2[3]))

        dmap_p2 = hv.DynamicMap(pn.bind(make_p2, timestep=datetimeIndexSlider))
        dmap_p2.cache_size = 1
        col2.append(pn.panel(pn.bind(getDatetime2, value=datetimeIndexSlider), align="center"))
        col2.append(pn.panel(dmap_p2, sizing_mode="stretch_both"))
        col2.sizing_mode = "stretch_both"

    animPane = pn.Column(pn.Row(pn.HSpacer(), datetimeIndexSlider, pn.HSpacer()), pn.Row(col1, col2, sizing_mode="stretch_both", styles={"flex": "2", "min-height": "0"}), sizing_mode="stretch_both")

    # Flux plots
    initFluxLocs = []
    for loc in ["EXPORT_CVP", "EXPORT_SWP", "PAST_CHIPPS"]:
        if loc in fluxLocs:
            initFluxLocs.append(loc)
    if len(initFluxLocs) == 0 and len(fluxLocs) > 0:
        initFluxLocs = [fluxLocs[0]]

    selectFluxLoc = pn.widgets.MultiSelect(name="loc", options=fluxLocs, value=initFluxLocs, size=8)

    # Define a callback function to prevent unselecting all options
    def preventUnselectAll(event):
        if len(selectFluxLoc.value) == 0:
            selectFluxLoc.value = event.old

    selectFluxLoc.param.watch(preventUnselectAll, "value")

    fluxLongList = []
    if fluxFile1 is not None:
        flux1long = pd.melt(flux1, id_vars="datetime", var_name="loc", value_name="flux")
        flux1long["file"] = "file 1"
        fluxLongList.append(flux1long)

    if fluxFile2 is not None:
        flux2long = pd.melt(flux2, id_vars="datetime", var_name="loc", value_name="flux")
        flux2long["file"] = "file 2"
        fluxLongList.append(flux2long)

    # Time series tab: one selectFluxLoc at top, line plots side by side
    fluxLineRow = pn.Row(sizing_mode="stretch_both")
    if fluxFile1 is not None:
        def make_flux1line(locs):
            return flux1long[flux1long["loc"].isin(locs)].hvplot.line(
                x="datetime", y="flux", xlabel="", by=["loc"],
                title=fluxFile1, responsive=True, height=350)
        fluxLineRow.append(pn.panel(hv.DynamicMap(pn.bind(make_flux1line, locs=selectFluxLoc)), sizing_mode="stretch_width"))

    if fluxFile2 is not None:
        def make_flux2line(locs):
            return flux2long[flux2long["loc"].isin(locs)].hvplot.line(
                x="datetime", y="flux", xlabel="", by=["loc"],
                title=fluxFile2, responsive=True, height=350)
        fluxLineRow.append(pn.panel(hv.DynamicMap(pn.bind(make_flux2line, locs=selectFluxLoc)), sizing_mode="stretch_width"))

    fluxLinePane = pn.Column(selectFluxLoc, fluxLineRow, sizing_mode="stretch_both")

    if len(fluxLongList) > 0:
        fluxLong = pd.concat(fluxLongList, ignore_index=True)

        def make_bar(timestep, locs):
            model_dt = anim1[anim1["datetimeIndex"] == timestep]["modelDatetime"].values[0]
            closest_dt = _flux_datetime[np.abs(_flux_datetime - model_dt).argmin()]
            filtered = fluxLong[(fluxLong["loc"].isin(locs)) & (fluxLong["datetime"] == closest_dt)]
            bar_width = max(150, len(locs) * 100)
            if len(fluxLongList) > 1:
                return filtered.hvplot.bar(x="loc", y="flux", by="file",
                                           xlabel="", ylabel="flux",
                                           frame_width=bar_width)
            else:
                return filtered.hvplot.bar(x="loc", y="flux",
                                           xlabel="", ylabel="flux",
                                           frame_width=bar_width)

        animPane.append(pn.Row(
            selectFluxLoc,
            pn.Column(
                pn.panel(pn.bind(make_bar, timestep=datetimeIndexSlider, locs=selectFluxLoc), sizing_mode="stretch_height"),
                scroll=True,
                sizing_mode="stretch_both",
            ),
            sizing_mode="stretch_width",
            styles={"flex": "1", "min-height": "0"},
        ))

    tabs = pn.Tabs(("Animation", animPane), ("Time series", fluxLinePane), sizing_mode="stretch_both")

    def _on_session_destroyed(session_context):
        import threading
        def _exit():
            import time
            time.sleep(0.01)
            os._exit(0)
        threading.Thread(target=_exit, daemon=True).start()

    pn.state.on_session_destroyed(_on_session_destroyed)
    server = tabs.show()
