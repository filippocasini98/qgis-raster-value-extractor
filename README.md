# qgis-raster-value-extractor

Overview
This QGIS processing tool extracts pixel values from multiple rasters at points inside a specified polygon (with optional internal buffering). The sampling grid is created by placing a point at the centroid of each grid cell used for sampling. The tool outputs the extracted data as a GeoPackage and CSV files.

Features
- Clip rasters to a field polygon boundary with optional buffer
- Create a dense point grid for sampling raster values (points are placed at the centroid of each grid cell)
- Support for single- and multi-band rasters with custom naming
- Export to GeoPackage (.gpkg) and CSV (.csv)
- Automatic loading of outputs into current QGIS project

Requirements
- QGIS 3.x or later
- Python 3 environment compatible with QGIS
- GDAL and QGIS Processing framework

Installation
1. Copy the script file `raster_value_extractor.py` into your QGIS Processing scripts folder.
2. Restart QGIS or refresh the Processing toolbox.
3. Find “Multiple Raster Value Extraction (GPKG + CSV)” under “Raster Analysis”.

Usage
1. Open the Processing Toolbox in QGIS.
2. Select the “Multiple Raster Value Extraction (GPKG + CSV)” tool.
3. Input your polygon layer defining the field area.
4. Select one or more rasters to sample.
5. Set an optional internal buffer distance (meters).
6. Specify the sampling grid resolution — points will be placed at the centroid of each grid cell.
7. Specify output file paths for GeoPackage and CSV or use defaults.
8. Run the tool. Outputs are added to the QGIS project.

Output
- A point vector layer with raster pixel values extracted per sampling point.
- GeoPackage and CSV files containing spatial coordinates and raster data.
