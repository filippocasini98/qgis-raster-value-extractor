"""
QGIS Script – Multiple Raster Value Extraction and Merge to GeoPackage & CSV
Author: Filippo Casini
Date: November 2025
"""

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterNumber,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsRectangle,
    QgsProcessingException,
)
from qgis import processing
import os
import re

# --------------------------------------------------------------------------- #
#   Algorithm definition
# --------------------------------------------------------------------------- #

class RasterValueExtractor(QgsProcessingAlgorithm):
    """
    Extract values from multiple rasters at the location of a field polygon,
    optionally applying an internal buffer, and write the results to a
    GeoPackage and a CSV file.
    """

    # --------------------------------------------------------------------- #
    #   Parameter names
    # --------------------------------------------------------------------- #

    INPUT_POLYGON  = 'INPUT_POLYGON'
    INPUT_RASTERS  = 'INPUT_RASTERS'
    OUTPUT_GPKG    = 'OUTPUT_GPKG'
    OUTPUT_CSV     = 'OUTPUT_CSV'
    BUFFER_SIZE    = 'BUFFER_SIZE'

    # --------------------------------------------------------------------- #
    #   Algorithm interface
    # --------------------------------------------------------------------- #

    def name(self) -> str:
        """Short, machine‑readable algorithm ID."""
        return 'rastervalueextractor'

    def displayName(self) -> str:
        """Human‑readable name shown in the QGIS toolbox."""
        return 'Multiple Raster Value Extraction (GPKG + CSV)'

    def group(self) -> str:
        """Group name shown in the toolbox."""
        return 'Raster Analysis'

    def groupId(self) -> str:
        """Group ID used internally by QGIS."""
        return 'rasteranalysis'

    def createInstance(self):
        """Create a fresh instance of the algorithm."""
        return RasterValueExtractor()

    # --------------------------------------------------------------------- #
    #   Parameter definition
    # --------------------------------------------------------------------- #

    def initAlgorithm(self, config=None):
        """Define the parameters that will be shown to the user."""
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_POLYGON,
                'Field polygon',
                [QgsProcessing.TypeVectorPolygon]
            )
        )

        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_RASTERS,
                'Rasters to process',
                QgsProcessing.TypeRaster
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.BUFFER_SIZE,
                'Internal buffer size (meters)',
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.0,
                minValue=0.0
            )
        )

        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_GPKG,
                'Output GeoPackage',
                'GPKG (*.gpkg)'
            )
        )

        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_CSV,
                'Output CSV',
                'CSV (*.csv)'
            )
        )

    # --------------------------------------------------------------------- #
    #   Main processing
    # --------------------------------------------------------------------- #

    def processAlgorithm(self, parameters, context, feedback):
        """Execute the algorithm."""
        # ------------------------------------------------------------------ #
        #   Read parameters
        # ------------------------------------------------------------------ #

        polygon_layer = self.parameterAsVectorLayer(parameters, self.INPUT_POLYGON, context)
        raster_layers  = self.parameterAsLayerList(parameters, self.INPUT_RASTERS, context)
        buffer_size    = self.parameterAsDouble(parameters, self.BUFFER_SIZE, context)

        if not polygon_layer or not polygon_layer.isValid():
            raise QgsProcessingException('Error: invalid field polygon.')

        if not raster_layers:
            raise QgsProcessingException('Error: no rasters selected.')

        # ------------------------------------------------------------------ #
        #   Create temporary folder for clipped TIFFs
        # ------------------------------------------------------------------ #

        temp_dir = os.path.join(QgsProject.instance().homePath() or os.path.expanduser('~'), 'temp_clip')
        os.makedirs(temp_dir, exist_ok=True)

        feedback.pushInfo('Starting processing…')

        # ------------------------------------------------------------------ #
        #   Clip each raster to the polygon
        # ------------------------------------------------------------------ #

        clipped_rasters = []
        total = len(raster_layers)

        for i, raster in enumerate(raster_layers):
            if feedback.isCanceled():
                break

            feedback.setProgress(int((i / max(total, 1)) * 30))

            raster_path = raster.source() if hasattr(raster, 'source') else str(raster)
            base_name   = os.path.splitext(os.path.basename(raster_path))[0]
            output_clip = os.path.join(temp_dir, f'{base_name}_clip.tif')

            feedback.pushInfo(f'Clipping raster: {base_name}')

            try:
                result = processing.run(
                    'gdal:cliprasterbymasklayer',
                    {
                        'INPUT': raster_path,
                        'MASK': polygon_layer,
                        'CROP_TO_CUTLINE': True,
                        'KEEP_RESOLUTION': True,
                        'OUTPUT': output_clip
                    },
                    context=context,
                    feedback=feedback
                )
                if result.get('OUTPUT') and os.path.exists(result['OUTPUT']):
                    clipped_rasters.append(result['OUTPUT'])
                else:
                    feedback.pushWarning(f'Could not save clipped raster: {base_name}')
            except Exception as e:
                feedback.pushWarning(f'Error clipping {base_name}: {e}')

        if not clipped_rasters:
            raise QgsProcessingException('No valid rasters after clipping.')

        # ------------------------------------------------------------------ #
        #   Load first clipped raster as reference for extent, resolution & CRS
        # ------------------------------------------------------------------ #

        ref_layer = QgsRasterLayer(clipped_rasters[0], 'raster_ref')
        if not ref_layer.isValid():
            raise QgsProcessingException('Error loading first clipped raster.')

        extent = ref_layer.extent()
        res_x  = ref_layer.rasterUnitsPerPixelX()
        res_y  = ref_layer.rasterUnitsPerPixelY()
        crs    = ref_layer.crs()

        # ------------------------------------------------------------------ #
        #   Create a point grid that covers the reference raster
        # ------------------------------------------------------------------ #

        center_x = extent.center().x()
        center_y = extent.center().y()

        width  = extent.width()
        height = extent.height()
        n_x    = int(width / res_x) + 1
        n_y    = int(height / res_y) + 1

        left   = center_x - (n_x * res_x) / 2
        bottom = center_y - (n_y * res_y) / 2
        right  = left + n_x * res_x
        top    = bottom + n_y * res_y

        grid_extent = QgsRectangle(left, bottom, right, top)

        feedback.pushInfo('Creating point grid…')
        feedback.setProgress(40)

        try:
            grid_res = processing.run(
                'qgis:creategrid',
                {
                    'TYPE': 0,          # Points
                    'EXTENT': grid_extent,
                    'HSPACING': res_x,
                    'VSPACING': res_y,
                    'CRS': crs,
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                },
                context=context,
                feedback=feedback
            )
            grid_layer = grid_res['OUTPUT']
        except Exception as e:
            raise QgsProcessingException(f'Grid creation failed: {e}')

        # ------------------------------------------------------------------ #
        #   Apply internal buffer to the polygon (if requested)
        # ------------------------------------------------------------------ #

        feedback.pushInfo('Applying internal buffer…')
        feedback.setProgress(45)

        if buffer_size > 0:
            try:
                buf_res = processing.run(
                    'native:buffer',
                    {
                        'INPUT': polygon_layer,
                        'DISTANCE': -buffer_size,   # Negative for inner buffer
                        'SEGMENTS': 5,
                        'END_CAP_STYLE': 0,
                        'JOIN_STYLE': 0,
                        'MITER_LIMIT': 2,
                        'DISSOLVE': False,
                        'OUTPUT': 'TEMPORARY_OUTPUT'
                    },
                    context=context,
                    feedback=feedback
                )
                mask_layer = buf_res['OUTPUT']
            except Exception as e:
                feedback.pushWarning(f'Buffer failed: {e}')
                mask_layer = polygon_layer
        else:
            mask_layer = polygon_layer

        # ------------------------------------------------------------------ #
        #   Clip the grid to the (buffered) polygon
        # ------------------------------------------------------------------ #

        feedback.pushInfo('Clipping grid to field boundary…')
        feedback.setProgress(50)

        try:
            clip_res = processing.run(
                'native:clip',
                {
                    'INPUT': grid_layer,
                    'OVERLAY': mask_layer,
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                },
                context=context,
                feedback=feedback
            )
            grid = clip_res['OUTPUT']
        except Exception as e:
            raise QgsProcessingException(f'Grid clipping failed: {e}')

        # ------------------------------------------------------------------ #
        #   Helpers for unique column names
        # ------------------------------------------------------------------ #

        def base_name_from_clip(path: str) -> str:
            """Return the raster name without the '_clip' suffix."""
            b = os.path.splitext(os.path.basename(path))[0]
            return b[:-5] if b.endswith('_clip') else b

        used_names = set()

        def unique_name(base: str) -> str:
            """Return a column name that is guaranteed to be unique."""
            n = base
            k = 1
            while n in used_names:
                n = f'{base}_{k}'
                k += 1
            used_names.add(n)
            return n

        def sort_by_suffix(names):
            """Sort names that end with a number (e.g. B1, B2)."""
            def keyfunc(n):
                m = re.search(r'(\d+)$', n)
                return int(m.group(1)) if m else 1
            return sorted(names, key=keyfunc)

        # ------------------------------------------------------------------ #
        #   Raster sampling
        # ------------------------------------------------------------------ #

        feedback.pushInfo('Sampling rasters…')
        feedback.setProgress(55)

        for i, r_path in enumerate(clipped_rasters):
            if feedback.isCanceled():
                break

            feedback.setProgress(55 + int((i / max(len(clipped_rasters), 1)) * 40))

            base = base_name_from_clip(r_path)
            final_base = unique_name(base)

            tmp_prefix = f'tmp{i}__'          # Temporary prefix used by the algorithm
            fields_before = [f.name() for f in grid.fields()]

            feedback.pushInfo(f'Extracting values from: {final_base}')

            try:
                res = processing.run(
                    'qgis:rastersampling',
                    {
                        'INPUT': grid,
                        'RASTERCOPY': r_path,
                        'COLUMN_PREFIX': tmp_prefix,
                        'OUTPUT': 'TEMPORARY_OUTPUT'
                    },
                    context=context,
                    feedback=feedback
                )
                grid = res['OUTPUT']
            except Exception as e:
                feedback.pushWarning(f'Error sampling {final_base}: {e}')
                continue

            # Identify new fields added by the sampling step
            all_names = [f.name() for f in grid.fields()]
            new_fields = [n for n in all_names if n.startswith(tmp_prefix)]
            if not new_fields:
                before_set = set(fields_before)
                new_fields = [n for n in all_names if n not in before_set]

            # Determine final column names (handle multi‑band rasters)
            new_fields_sorted = sort_by_suffix(new_fields)
            if len(new_fields_sorted) <= 1:
                final_names = [final_base]
            else:
                final_names = [unique_name(f'{final_base}_B{j+1}') for j in range(len(new_fields_sorted))]

            # Rename the temporary columns
            try:
                rename_map = {}
                for old, new in zip(new_fields_sorted, final_names):
                    if old == new:
                        continue
                    idx = grid.fields().indexOf(old)
                    if idx != -1:
                        rename_map[idx] = new

                if rename_map:
                    grid.startEditing()
                    ok = grid.dataProvider().renameAttributes(rename_map)
                    grid.updateFields()
                    if not ok:
                        grid.rollBack()
                        feedback.pushWarning('Field renaming failed for one or more fields.')
                    else:
                        grid.commitChanges()
            except Exception as e:
                feedback.pushWarning(f'Error renaming fields for {final_base}: {e}')

        # ------------------------------------------------------------------ #
        #   Write output files
        # ------------------------------------------------------------------ #

        feedback.pushInfo('Writing final outputs…')
        feedback.setProgress(95)

        out_gpkg = self.parameterAsFileOutput(parameters, self.OUTPUT_GPKG, context)
        out_csv  = self.parameterAsFileOutput(parameters, self.OUTPUT_CSV, context)

        # Default paths if the user left the fields blank
        project_path = QgsProject.instance().homePath() or os.path.dirname(polygon_layer.source())
        if not out_gpkg:
            out_gpkg = os.path.join(project_path, 'raster_values.gpkg')
        if not out_csv:
            out_csv = os.path.join(project_path, 'raster_values.csv')

        # Ensure the output directories exist
        for p in (out_gpkg, out_csv):
            os.makedirs(os.path.dirname(p), exist_ok=True)

        # Save as GeoPackage
        if out_gpkg:
            try:
                QgsVectorFileWriter.writeAsVectorFormat(
                    grid,
                    out_gpkg,
                    'utf-8',
                    grid.crs(),
                    'GPKG'
                )
                feedback.pushInfo(f'GeoPackage written to {out_gpkg}')
            except Exception as e:
                feedback.pushWarning(f'Failed to write GeoPackage: {e}')

        # Save as CSV
        if out_csv:
            try:
                QgsVectorFileWriter.writeAsVectorFormat(
                    grid,
                    out_csv,
                    'utf-8',
                    grid.crs(),
                    'CSV'
                )
                feedback.pushInfo(f'CSV written to {out_csv}')

                # Load the CSV back into QGIS for quick inspection
                csv_layer = QgsVectorLayer(out_csv, 'Raster values (CSV)', 'ogr')
                if csv_layer.isValid():
                    QgsProject.instance().addMapLayer(csv_layer)
                    feedback.pushInfo('CSV layer added to the project')
                else:
                    feedback.pushWarning(f'Could not load CSV: {out_csv}')
            except Exception as e:
                feedback.pushWarning(f'Failed to write CSV: {e}')

        # Load the GeoPackage layer into the project
        if out_gpkg and os.path.exists(out_gpkg):
            gpkg_layer = QgsVectorLayer(out_gpkg, 'Raster values', 'ogr')
            if gpkg_layer.isValid():
                QgsProject.instance().addMapLayer(gpkg_layer)
                feedback.pushInfo('GeoPackage layer added to the project')

        feedback.pushInfo('Processing finished!')
        feedback.setProgress(100)

        # Return the paths to the created files
        return {self.OUTPUT_GPKG: out_gpkg, self.OUTPUT_CSV: out_csv}

# --------------------------------------------------------------------------- #
#   Registration function – called by QGIS
# --------------------------------------------------------------------------- #

def classFactory(iface):
    """Return a new instance of the algorithm when QGIS loads it."""
    return RasterValueExtractor()
