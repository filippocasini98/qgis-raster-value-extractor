# qgis-raster-value-extractor
The tool clips rasters to a field polygon (with optional buffer), creates a dense point grid inside it, and samples raster pixel values at each point. It outputs a GeoPackage and optional CSV with all extracted values per point, supporting multi-band rasters, and loads results into QGIS for analysis.
