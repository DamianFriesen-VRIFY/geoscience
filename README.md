# QGIS Geoscience Plugin
## Now with drill sections!

*Author: Roland Hill - Please contribute and make this a better, more comprehensive geoscience tool.*

**Geoscience** provides useful tools to geoscientists. This includes drill hole processing, display of downhole data in plan. Version 1.0 also brings creation and display of drill sections with downhole data and elevation layers. Other utilities help with raster and vector manipulation.

See https://www.spatialintegration.com/geoscience-plugin-for-qgis/ for detailed instructions.

## Drill Tools 

Tools to display drill holes, down hole data and sections in QGIS. This includes de-surveying the holes using collar azimuth and dip or a survey table if available. Prior to using Drill Tools you need to open the collar, survey (optional) and down hole data (optional) tables in QGIS. You can use any local format supported by QGIS including shapefiles, MapInfo Tab files or CSV files. To open data using CSV, use the existing Delimited Text tool 

**Drill Tools will only work with projected coordinate systems (ie not latitude and longitude)**

## Vector Tools

![https://rolandhill.github.io/geoscience/icon/ReverseLine.png](https://rolandhill.github.io/geoscience/icon/ReverseLine.png)

Reverses the order of all the nodes in the selected line features, in effect reversing the direction of the line. This is necessary when using asymmetric line styles such as reverse and normal fault symbols. Note that the layer must be editable before using the tool.

## Raster Tools

![https://rolandhill.github.io/geoscience/icon/WhiteTransparent.png](https://rolandhill.github.io/geoscience/icon/WhiteTransparent.png)

Sets the transparent colour to **white** for all the raster images selected in the project tree. To use, first select all the rasters you wish to process using control and shift left clicks, then choose this menu entry or
toolbar button. Ideal for image sets such as EM channels or hyperspectral images.

![https://rolandhill.github.io/geoscience/icon/BlackTransparent.png](https://rolandhill.github.io/geoscience/icon/BlackTransparent.png)

Sets the transparent colour to **black** for all the raster images selected in the project tree. To use, first select all the rasters you wish to process using control and shift left clicks, then choose this menu entry or toolbar button. Ideal for image sets such as EM channels or hyperspectral images.

## Local Grid
Calculates the WKT representation of a local grid from 2 or more coordinates known in both the local and recognised base projected coordinate system (eg WGS84 UTM55S, GDA94 MGA55 etc). If you have 3 or more points then the local grid definition will be 3 dimensional (make sure there is separation in Z value a well). If the coordinate pairs have error in them then a best fit will be used. The generated local grid CRS must then be manually pasted into a Custom CRS definition. A local CRS can be re-projected on the fly, converted etc like any other CRS.

## No longer in development due to funded OpenLog development by Oslandia

* Released under GPL license.

---

## Standalone Desurvey Tool for VSCode

A standalone Python-based drill hole desurvey tool that works independently without QGIS. Provides GUI interface for field matching, 3D shapefile export, and comprehensive QC reporting.

### Features

- **Minimum Curvature Desurvey**: Industry-standard quaternion-based calculations
- **GUI Interface**: User-friendly tkinter interface with field mapping
- **3D Shapefiles**: Export collar points, drill traces, intervals, and interval mid-points
- **QC Reports**: Comprehensive HTML quality control reports with interactive 3D visualization
- **Flexible Input**: Supports CSV files with auto-detection of column names
- **Coordinate Systems**: Configurable EPSG coordinate reference systems

### Limitations

1. **Projected Coordinates Only**: The tool only works with projected coordinate systems (e.g., UTM, local grids). Latitude/longitude (WGS84, NAD83) coordinates are **not supported** and will produce incorrect results.

2. **CSV Input Format**: Input files must be in CSV format. Other formats (Excel, shapefiles, databases) are not directly supported and must be converted to CSV first.

3. **Column Name Matching**: While the tool auto-detects common column names, it may not recognize all variations. Users should verify field mappings in the GUI before processing.

4. **Memory Constraints**: Very large datasets (hundreds of thousands of survey points or intervals) may cause performance issues or memory errors depending on available system RAM.

5. **Desurvey Method**: Only the minimum curvature method is implemented. Other methods (tangential, balanced tangential, etc.) are not available.

6. **Survey Validation**: The tool performs basic data quality checks but does not validate the geological or engineering validity of survey measurements.

7. **3D Visualization**: The interactive 3D plot in QC reports requires an internet connection to load the Plotly JavaScript library from CDN.

8. **Shapefile Limitations**: 
   - Field names are truncated to 10 characters (ESRI Shapefile format limitation)
   - Some special characters in field names may be removed or replaced
   - Maximum file size constraints apply to individual shapefiles

9. **Coordinate Precision**: Coordinates are calculated to millimeter precision but stored with 3 decimal places in shapefiles (meter-level precision).

10. **No Real-time Preview**: Changes to parameters require re-running the entire desurvey process; there is no live preview of results.

### Installation

```bash
# Create virtual environment
python -m venv venv_desurvey

# Activate (Windows)
venv_desurvey\Scripts\activate

# Install dependencies
pip install -r requirements_standalone.txt
```

### Usage

```bash
# Launch GUI
python desurvey_gui.py
```

