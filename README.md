# qgis-raster-value-extractor

Overview
This QGIS processing tool extracts pixel values from multiple rasters at points inside a specified polygon (with optional internal buffering). It outputs the extracted data as a GeoPackage and CSV file, facilitating spatial analysis and reporting.

Features
Clip rasters to a field polygon boundary with optional buffer

Create a dense point grid for sampling raster values

Support for single and multi-band rasters with custom naming

Export to GeoPackage (.gpkg) and CSV (.csv)

Automatic loading of outputs into current QGIS project

Requirements
QGIS 3.x or later

Python 3 environment compatible with QGIS

GDAL and QGIS Processing framework

Installation
Copy the script file ‘raster_value_extractor.py’ into your QGIS Processing scripts folder

Restart QGIS or refresh the Processing toolbox

Find “Multiple Raster Value Extraction (GPKG + CSV)” under “Raster Analysis”

Usage
Open the Processing Toolbox in QGIS.

Select the “Multiple Raster Value Extraction (GPKG + CSV)” tool.

Input your polygon layer defining the field area.

Select one or more rasters to sample.

Set an optional internal buffer distance (meters).

Specify output file paths for GeoPackage and CSV or use defaults.

Run the tool. Outputs are added to the QGIS project.

Output
A point vector layer with raster pixel values extracted per point.

GeoPackage and CSV files containing spatial coordinates and raster data.
