import json
import logging
from .pdgstaging import logging_config
import os
from pdgstaging import TilePathManager
import warnings
from coloraide import Color
import colormaps as cmaps

logger = logging_config.logger


class ConfigManager:
    """
    A Config Manager is a tool that simplifies working with the tiling
    configuration. The tiling configuration specifies which TileMatrixSet
    (tms) to use, how to summarize vector data into raster values, which
    z-range to create tiles for, etc.

    The config object, passed as an argument when initializing a
    ConfigManager, is a dictionary with the properties listed below. To see
    all of the default values for the config object, see the
    ConfigManager.defaults property.

    - Directory paths and filenames. Where input data is read from and
      output data is written to. The only required property is the
      'dir_input' property. Otherwise, directories will be created in the
      current working directory.
        - dir_input: str
            The directory to read input vector files from.
        - dir_staged: str
            The directory to save staged files to.
        - dir_geotiff : str
            The directory to save GeoTIFF files to.
        - dir_web_tiles : str
            The directory to save web tiles to.
        - dir_3dtiles: str
            The directory to save 3D tiles to.
        - dir_footprints: str
            The directory to read footprint files from. Required only if
            the 'deduplicate_method' is 'footprints'. A footprint is a
            vector file with a polygon that defines the boundary of an
            associated input file. There should be one footprint file for
            each input file, with the same name as the input file. Polygons
            in footprint files must also have at least one property that
            can be used to rank files according to preference. Polygons
            from lower-ranked files will be removed where footprints
            overlap.
        - filename_staging_summary : str
            The path and filename to save a CSV file that summarizes the
            tiled files that were created during the staging process.
        - filename_rasterization_events : str
            The path and filename to save a CSV file that summarizes the
            rasterization events that happened during the rasterization
            process (in the viz-rasterize step).
        - filename_rasters_summary : str
            The path and filename to save a CSV file that summarizes the
            data from the rasters that were created during the
            rasterization process.
        - filename_config : str
            The path to the config file. This property will be set
            automatically if the config is passed as a path string. When
            the config is updated, it will be saved to this filename, but
            with a suffix indicating that it is an updated.

    - Filetypes for input and output data.
        - ext_input : str
            The file extension of input files, e.g. '.shp' or '.gpkg'.
        - ext_staged : str
            The file extension to use for staged vector files, e.g. '.shp'
            or '.gpkg'.
        - ext_web_tiles : str
            The file extension to use for web tiles, e.g. '.png' or '.jpg'.
        - ext_footprints: str
            The file extension of footprint files, e.g. '.shp' or '.gpkg'.

    - Properties. Names of properties added to polygons created during
      processing. These names cannot already exist in the input data. It is
      unlikely that you will need to change these properties from their
      default values (only if there are existing conflicting properties in
      your input data).
        - prop_centroid_x : str
            The name of the property that indicates the x-coordinate of the
            centroid of the polygon. Defaults to 'staging_centroid_x',
        - prop_centroid_y : str
            The name of the property that the property that indicates the
            y-coordinate of the centroid of the polygon. Defaults to
            'staging_centroid_y',
        - prop_area : str
            The name of the property that contains the calculated area of
            the polygon. Defaults to 'staging_area',
        - prop_tile : str
            The name of the property that indicates which tile the polygon
            belongs to (for this property, a polygon belongs to a tile if
            it intersects it.) . Defaults to 'staging_tile',
        - prop_centroid_tile : str
            The name of the property that indicates which tile the
            polygon's centroid falls within. Defaults to
            'staging_centroid_tile',
        - prop_filename : str
            The name of the property that indicates the filename from which
            the polygon originated, before staging. Defaults to
            'staging_filename',
        - prop_identifier : str
            The name of the the property that gives a unique ID to the
            polygon. Defaults to 'staging_identifier',
        - prop_centroid_within_tile : str
            The name of the boolean property that indicates if a polygon's
            tile property matches it's centroid property. Defaults to
            'staging_centroid_within_tile'
        - prop_duplicated : str
            The name of the boolean property that indicates if a polygon
            was identified as a duplicate or not

    - Staging options.
        - input_crs : str
            If the input data is lacking CRS information, then the CRS of
            the input data. This will overwrite existing CRS data, if
            GeoPandas detects any. Input data will not be reprojected to
            this CRS.
        - simplify_tolerance : float
            The tolerance to use when simplifying the input polygons.
            Defaults to 0.0001. Set to None to skip simplification.

    - Tiling & rasterization options.
        - tms_id : str
            The ID of the TMS to use. Must much a TMS supported by the
            morecantile library. Defaults to 'WGS1984Quad'.
        - tile_path_structure : list of int
            A list of strings that represent the directory structure of
            last segment of the path that uses the tms (TileMatrixSet),
            style (layer/statistic), x index (TileCol), y index (TileRow),
            and z index (TileMatrix) of the tile. By default, the path will
            be in the format of
            {TileMatrixSet}/{Style}/{TileMatrix}/{TileCol}/{TileRow}.ext,
            configured as ('style', 'tms', 'z', 'x', 'y'). The x, y, z
            indices must always be last in the list. ('tms', 'style', 'z',
            'x', 'y'),
        - z_range : tuple of int
            The minimum and maximum z levels to create tiles for, e.g. (0,
            13). Tiled vector files will be created for the maximum z
            level. GeoTIFF and webtiles will be created for all z-levels.
            Defaults to (0, 13)
        - tile_size : tuple of int
            The pixel size (width, height) of the GeoTiffs and webtiles to
            create. Defaults to (256, 256).
        - statistics : list of dict
            A list of statistics and options to use to convert vector data
            into raster data. For each item in the list, a separate band
            will be created in GeoTIFF files, and a separate layer will be
            created for web tiles. The statistics list is a list of
            dictionaries. Each dictionary contains the following
            properties:
                - name : str
                    The name of the statistic. Can be anything but must be
                    unique.
                - weight_by : 'count' or 'area'
                    The weighting method for the statistic. Options are
                    'count' and 'area'. 'count' indicates that the
                    statistic is calculated based on the number of polygons
                    in each cell (location is identified by the centroid of
                    the polygon). 'area' indicates that the statistic is
                    calculated based on the area of the polygons that cover
                    each cell.
                - property : str
                    The name of the property in the vector file to
                    calculate the statistic for. Besides the properties
                    that are available from the input vector data, the
                    following keywords can be used:
                        'centroids_per_pixel' : The number of polygons with
                            centroids that fall in the cell/pixel. (Only
                            available if weight_by is 'count')
                        'area_within_pixel' : The area of the
                            polygon that falls within a given cell/pixel,
                            in the units of the CRS. (Only available if
                            weight_by is 'area')
                        'area_per_pixel_area' : Same as
                            'area_within_pixel', but divided by the area of
                            the cell/pixel. (Only available if weight_by is
                            'area')
                - aggregation_method : str
                    The function to be applied to the property. The vector
                    data will first be grouped into cells, then the
                    aggregation method will be used to summarize the given
                    property in the cell. Method can be any method allowed
                    in the 'func' property of the panda's aggregate method,
                    e.g. 'sum', 'count', 'mean', etc.
                - resampling_method : str
                    The resampling method to use when combining raster data
                    from child tiles into parent tiles. See rasterio's
                    Resampling Methods for list of the available methods.
                - val_range : tuple of float or list of float
                    A min and max value for the statistic. This is used for
                    consistency when mapping the color palette to the pixel
                    values during web tile image generation. When a min or
                    max value within a val_range is set to None, then a min
                    or max value will be calculated for the each z-level
                    for which geotiffs are created.
                - palette : list of str or str
                    Colors to map to pixel values when creating web-tiles.
                    Can be provided as a list of color strings in any
                    format accepted by the coloraide library (see:
                    https://facelessuser.github.io/coloraide/color/), or
                    the name of a colormap from the colormaps library (see:
                    https://pratiman-91.github.io/colormaps). Colors with
                    transparency hex codes are accepted (see:
                    https://gist.github.com/lopspower/03fb1cc0ac9f32ef38f4)
                - nodata_val: int or float or None or np.nan
                    The value of pixels to interpret as no data or missing
                    data. Defaults to None.
                - nodata_color: str
                    When mapping pixel values to colors, the color to use
                    for pixels with the no data value.
                - z_config : dict
                    A dict of config options specific to each z-level.
                    Currently, only setting a val_range is supported.
                    Eventually, this could be used to set z-specific tile
                    sizes and color palettes.

        - 3D Tile options:
            - version: str
                An optional version code that identifies this worklflow run
                can be set. Currently, the version is only added to the
                3dtiles tileset.json asset property.
            - geometricError: float
                An optional geometric error to use for all of the 3D tiles.
            - z_coord: float
                For input data that has only x and y coordinates, a
                z-coordinate to use for the 3D tiles. Default is 0.

        - Deduplication options. Deduplicate input that comes from multiple
          source files.
            - deduplicate_at : list of str or None
                When to remove the polygons identified as duplicates.
                Options are 'staging', 'raster', '3dtiles', or None to skip
                deduplication. If set to 'staging', then duplicates will
                also be removed in raster and 3dtiles.
            - deduplicate_method : 'footprints', 'neighbor', or None
                The method to use for deduplication. Options are
                'neighbor', 'footprints', or None. If None, then no
                deduplication will be performed. If 'footprints',
                then the input data will be deduplicated by removing
                polygons that are contained within sections of overlapping
                file footprints. This method requires footprint vector
                files that have the same name as the input vector files,
                stored in a directory specified by the 'dir_footprints'
                option. If 'neighbor', then the input data will be
                deduplicated by removing nearby or overlapping polygons,
                as determined by the 'deduplicate_centroid_tolerance' and
                'deduplicate_overlap_tolerance' options.
            - deduplicate_keep_rules : list of tuple: []
                Required for both deduplication methods. Rules that define
                which of the polygons to keep when two or more are
                duplicates. A list of tuples of the form (property,
                operator). The property is the name of the property in the
                input file (in the case of neighbor deduplication) or in
                the footprint file (in the case of footprint
                deduplication). The operator is the comparison operator to
                use. If the operator is 'larger', the polygon with the
                largest value for the property will be kept, and vice versa
                for 'smaller. When two properties are equal, then the next
                property in the list will be checked.
            - deduplicate_overlap_tolerance : float, optional
                For the 'neighbor' deduplication method only. The minimum
                proportion of a polygon's area that must be overlapped by
                another polygon to be considered a duplicate. Default is
                0.5. Set to None to ignore overlap proportions when
                comparing polygons, and set a centroid threshold instead.
                Note that both an overlap_tolerance AND a
                centroid_tolerance can be used.
            - deduplicate_overlap_both : bool, optional
                For the 'neighbor' deduplication method only. If True, then
                the overlap_tolerance proportion must be True for both of
                the intersecting polygons to be considered a duplicate. If
                False, then the overlap_tolerance proportion must be True
                for only one of the intersecting polygons to be considered
                a duplicate. Default is True.
            - deduplicate_centroid_tolerance : float, optional
                For the 'neighbor' deduplication method only. The maximum
                distance between the centroids of two polygons to be
                considered a duplicate. Default is None. Set to None to
                ignore centroid distances when comparing polygons, and set
                an overlap threshold instead. Note that both an
                overlap_tolerance AND a centroid_tolerance can be used. The
                unit of the distance is the unit of the distance_crs
                property (e.g. meters for EPSG:3857), or the unit of the
                GeoDataFrame if distance_crs is None.
            - deduplicate_distance_crs : str, optional
                For the 'neighbor' deduplication method only. The CRS to
                use for the centroid distance calculation. Default is
                EPSG:3857. Centroid points will be re-projected to this CRS
                before calculating the distance between them.
                centroid_tolerance will use the units of this CRS. Set to
                None to skip the re-projection and use the CRS of the
                GeoDataFrame.
            - deduplicate_clip_to_footprint : bool, optional
                For the 'footprints' deduplication method only. If True,
                then polygons that fall outside the bounds of the
                associated footprint will be removed. Default is True for this
                release, but will be false for future releases.
            - deduplicate_clip_method: str, optional
                For the 'footprints' deduplication method only, when
                deduplicate_clip_to_footprint is True. The method to use to
                determine if a polygon falls within the footprint. The
                method is used as the the predicate for an sjoin operation
                between the polygons GDF and the footprint GDF. Can be one
                of: 'contains', 'contains_properly', 'covers', 'crosses',
                'intersects', 'overlaps', 'touches', 'within' (any option
                listed by
                geopandas.GeoDataFrame.sindex.valid_query_predicates).
                Defaults to 'intersects'.

    Example config:
    ---------------

    {
        "dir_geotiff": "/path/to/geotiff/dir",
        "dir_web_tiles": "/path/to/web/tiles/dir",
        "dir_staged": "/path/to/staged/dir",
        "dir_input": "/path/to/input/dir",
        "filename_staging_summary": "staging_summary.csv",
        "ext_web_tiles": ".png",
        "ext_input": ".shp",
        "ext_staged": ".gpkg",
        "statistics": [
            {
                "name": "polygon_count",
                "weight_by": "count",
                "property": "centroids_per_pixel",
                "aggregation_method": "sum",
                "resampling_method": "sum",
                "val_range": [0, None],
                "palette": ["#ffffff", "#000000"]
            },
            {
                "name": "coverage",
                "weight_by": "area",
                "property": "area_per_pixel_area",
                "aggregation_method": "sum",
                "resampling_method": "average",
                "val_range": [0,1],
                "palette": ["red", "blue"],
                "z_config": {
                    0: {
                        "val_range": [0,0.5],
                    }, ...
                }
            }
        ]
    }
    """

    defaults = {
        # Directory paths for input and out put
        "version": None,
        "dir_geotiff": "geotiff",
        "dir_web_tiles": "web_tiles",
        "dir_3dtiles": "3dtiles",
        "dir_staged": "staged",
        "dir_input": "input",
        "dir_footprints": "footprints",
        "filename_staging_summary": "staging_summary.csv",
        "filename_rasterization_events": "rasterization_events.csv",
        "filename_rasters_summary": "rasters_summary.csv",
        "filename_config": "config.json",
        # File types for input and output
        "ext_web_tiles": ".png",
        "ext_input": ".shp",
        "ext_staged": ".gpkg",
        "ext_footprints": ".gpkg",
        # Names of properties added to polygons, created during processing
        "prop_centroid_x": "staging_centroid_x",
        "prop_centroid_y": "staging_centroid_y",
        "prop_area": "staging_area",
        "prop_tile": "staging_tile",
        "prop_centroid_tile": "staging_centroid_tile",
        "prop_filename": "staging_filename",
        "prop_identifier": "staging_identifier",
        "prop_centroid_within_tile": "staging_centroid_within_tile",
        "prop_duplicated": "staging_duplicated",
        # original CRS if not set in input
        "input_crs": None,
        # Staging options
        "simplify_tolerance": 0.0001,
        # Tiling & rasterization options
        "tms_id": "WGS1984Quad",
        "tile_path_structure": ("style", "tms", "z", "x", "y"),
        "z_range": (0, 13),
        "tile_size": (256, 256),
        "statistics": [
            {
                "name": "polygon_count",
                "weight_by": "count",
                "property": "centroids_per_pixel",
                "aggregation_method": "sum",
                "resampling_method": "sum",
                "val_range": [0, None],
                "nodata_val": 0,
                "nodata_color": "#ffffff00",
            },
            {
                "name": "coverage",
                "weight_by": "area",
                "property": "area_per_pixel_area",
                "aggregation_method": "sum",
                "resampling_method": "average",
                "val_range": [0, 1],
                "nodata_val": 0,
                "nodata_color": "#ffffff00",
            },
        ],
        "geometricError": None,
        "z_coord": 0,
        # Deduplication options. Do not deduplicate by default.
        "deduplicate_at": None,
        "deduplicate_method": None,
        "deduplicate_keep_rules": [],
        "deduplicate_overlap_tolerance": 0.5,
        "deduplicate_overlap_both": True,
        "deduplicate_centroid_tolerance": None,
        "deduplicate_distance_crs": "EPSG:3857",
        "deduplicate_clip_to_footprint": True,
        "deduplicate_clip_method": "intersects",
    }

    tiling_scheme_map = {
        # A tiling scheme for geometry referenced to a simple
        # GeographicProjection where longitude and latitude are directly
        # mapped to X and Y. This projection is commonly known as
        # geographic, equirectangular, equidistant cylindrical, or plate
        # carrée.
        "GeographicTilingScheme": ["WorldCRS84Quad", "WGS1984Quad"],
        # A tiling scheme for geometry referenced to a
        # WebMercatorProjection, EPSG:3857. This is the tiling scheme used
        # by Google Maps, Microsoft Bing Maps, and most of ESRI ArcGIS
        # Online.
        "WebMercatorTilingScheme": ["WebMercatorQuad", "WorldMercatorWGS84Quad"],
    }

    def __init__(self, config=None):
        """
        Parameters
        ----------
        config : dict or str
            The tiling config object or a path to a JSON file containing
            the tiling config object.
        """

        if isinstance(config, str):
            path = config
            config = self.read(path)
            if config.get("filename_config") is None:
                config["filename_config"] = path

        if not isinstance(config, dict):
            raise ValueError("config must be a dict or a path to a JSON file")

        self.input_config = config
        self.config = self.defaults | config
        # Save a copy of the original config object, since we will be modifying
        # it
        self.original_config = self.config.copy()

        self.tiles = TilePathManager(**self.get_path_manager_config())

        # Make a shortcut to the property names
        self.props = {}
        for k in self.config.keys():
            if k.startswith("prop_"):
                prop_name = k.removeprefix("prop_")
                self.props[prop_name] = self.config[k]

    def write(self, updated=False):
        """
        Save the configuration to a JSON file.

        Parameters
        ----------
        updated : boolean
            If True, then a suffix will be added to the filename to
            indicate that it is an updated version.
        """
        filename = self.get("filename_config")
        if updated:
            filename = "{0}_{2}{1}".format(*os.path.splitext(filename), "_updated")
        # TODO: Don't save default values
        with open(filename, "w") as f:
            json.dump(self.config, f, indent=4)

    def read(self, filename):
        """
        Load the configuration from a file.

        Parameters
        ----------
        filename : str
            The file to load from.

        Returns
        -------
        config : dict
            The configuration dictionary.
        """
        with open(filename, "r") as f:
            config = json.load(f)
        return config

    def set(self, key, value):
        """
        Add a property to the config object.

        Parameters
        ----------
        key : str
            The key to add.
        value : any
            The value to add.
        """
        self.config[key] = value

    def get(self, key):
        """
        Get a property from the config object.

        Parameters
        ----------
        key : str
            The key to get.

        Returns
        -------
        any
            The property.
        """
        return self.config.get(key)

    def polygon_prop(self, prop):
        """
        Get the configured property name for new properties created by the
        tiling process.

        Parameters
        ----------
        prop : 'centroid_x' or 'centroid_y' or 'area' or
                'tile' or 'centroid_tile' or 'filename' or 'identifier' or
                'centroid_within_tile'
            The property.
        """
        return self.get("prop_" + prop)

    def get_config_names(self):
        """
        Get all property names from the config object.

        Returns
        -------
        list
            The property names.
        """
        return list(self.config.keys())

    def get_config_values(self):
        """
        Get all property values from the config object.

        Returns
        -------
        list
            The property values.
        """
        return list(self.config.values())

    def get_min_z(self):
        """
        Get the minimum z level. (The lowest resolution level)
        """
        return self.get("z_range")[0]

    def get_max_z(self):
        """
        Get the maximum z level. (The highest resolution level)
        """
        return self.get("z_range")[1]

    def get_colors(self):
        """
        Get the colors set for each statistic in the config object,
        ignoring the no data color.
        """
        return [stat.get("palette") for stat in self.config["statistics"]]

    def get_palettes(self):
        """
        Get the colors set for each statistic in the config object,
        including the no data color. Each item in the return list can be
        used in instantiate a pdgraster.Palette with a color gradient and
        nodata color.

        Returns
        -------
        list
            The palettes, in the following format:
            [
                [['stat1_col1', 'stat1_col2', ...], 'stat1_nodata_col' ],
                [['stat2_col1', 'stat2_col2', ...], 'stat2_nodata_col' ],
                ['stat3_colormap_name', 'stat3_nodata_col'],
                ...
            ]
        """
        palettes = []
        for stat in self.config["statistics"]:
            colors = stat.get("palette")
            nodata_color = stat.get("nodata_color")
            palette = [colors, nodata_color]
            palettes.append(palette)
        return palettes

    def get_stat_names(self):
        """
        Get all statistic names from the config object.

        Returns
        -------
        list
            The statistic names.
        """
        return [stat["name"] for stat in self.config["statistics"]]

    def get_stat_count(self):
        """
        Return the number of statistics.

        Returns
        -------
        int
            The number of statistics.
        """
        return len(self.config["statistics"])

    def get_stat_config(self, stat=None):
        """
        Get the configuration for a statistic.

        Parameters
        ----------
        statistic : str
            The statistic name.

        Returns
        -------
        dict
            The statistic configuration.
        """
        stats_list = self.config["statistics"]
        # Find the stat in stat_list that has the given name
        for stat_config in stats_list:
            if stat_config["name"] == stat:
                return stat_config
        # If no stat with that name is found, return None
        return None

    def get_nodata_vals(self):
        """
        Get the nodata values for each statistic in the config object.

        Returns
        -------
        list
            The nodata values.
        """
        stat_names = self.get_stat_names()
        stat_configs = [self.get_stat_config(stat) for stat in stat_names]
        return [stat.get("nodata_val") for stat in stat_configs]

    def get_resampling_methods(self):
        """
        Return a list of resampling methods names from all the
        statistics.

        Returns
        -------
        list
            A list of resampling methods.
        """
        resampling_methods = []
        for stat in self.config["statistics"]:
            resampling_methods.append(stat["resampling_method"])
        return resampling_methods

    def get_metacatui_raster_configs(self, base_url=""):
        """
        Return a dictionary that can be used to configure a 3d tile layer
        in a MetacatUI Cesium map.

        Parameters
        ----------
        base_url : str The url to where the layers will be hosted. If not
        set then, paths will be relative starting with the TMS ID.

        Returns
        -------
        list
            The metacatui configuration objects as dicts
        """

        tms = self.get("tms_id")
        stats = self.get_stat_names()
        index_order = list(self.get("tile_path_structure"))
        ext = self.get("ext_web_tiles")
        tsm = self.tiling_scheme_map
        max_z = self.get_max_z()

        index_map = {
            "style": "",
            "tms": tms,
            "z": "{TileMatrix}",
            "x": "{TileCol}",
            "y": "{TileRow}",
        }

        # Get the tilingScheme
        scheme = "WebMercatorTilingScheme"
        scheme_match = [s for s, t in tsm.items() if tms in t]
        if len(scheme_match) == 0:
            warnings.warn(
                f"Cesium does not support the tiling scheme: {tms},"
                " using a default WebMercatorTilingScheme."
            )
        else:
            scheme = scheme_match[0]

        # Get the bounds:
        try:
            bounds = self.tiles.get_total_bounding_box("web_tiles", max_z)
        except ValueError:
            try:
                bounds = self.tiles.get_total_bounding_box("staged")
            except ValueError:
                try:
                    bounds = self.tiles.get_total_bounding_box("geotiff", max_z)
                except ValueError:
                    try:
                        bounds = self.tiles.get_total_bounding_box("3dtiles", max_z)
                    except ValueError:
                        warnings.warn(
                            "Tile files could not be found. The cesium "
                            "rectangle option will not be set, and Cesium will"
                            " assume that the layer covers the entire world."
                        )
                        bounds = None

        layer_configs = []

        for stat in stats:

            # make the URl
            index_map["style"] = stat
            path_parts = [index_map[i] for i in index_order]
            path_parts[-1] += ext
            url = os.path.join(base_url, *path_parts)

            # Get the color palette
            color_palette = self.get_stat_config(stat)["palette"]

            color_objs = []
            if isinstance(color_palette, list):
                # convert all to hex codes.
                colors = [self.to_hex(c) for c in color_palette]
            elif isinstance(color_palette, str):
                colors = self.color_list_from_cmaps(color_palette)
            num_cols = len(colors)
            # Get min and max. As the Cesium map doesn't support a different
            # palette for each z-level yet, just use the max_z palette
            minv = self.get_min(stat=stat, z=max_z, sub_general=True)
            maxv = self.get_max(stat=stat, z=max_z, sub_general=True)
            for i in range(num_cols):
                color_objs.append(
                    {
                        "color": colors[i],
                        "value": minv + (maxv - minv) * (i / (num_cols - 1)),
                    }
                )

            layer_configs.append(
                {
                    "type": "WebMapTileServiceImageryProvider",
                    "label": stat,
                    "cesiumOptions": {
                        "url": url,
                        "tilingScheme": scheme,
                        "rectangle": bounds,
                    },
                    "colorPalette": {
                        "paletteType": "continuous",
                        "property": stat,
                        "colors": color_objs,
                    },
                }
            )

        return layer_configs

    def get_metacatui_3dtiles_config(self, base_url="", color=None):
        """
        Return a dictionary that can be used to configure a 3d tile layer
        in a MetacatUI Cesium map.

        Parameters
        ----------
        base_url : str
            The url to where the layers will be hosted. If not set then,
            paths will be relative starting with the TMS ID.
        color : str
            The color to use for the 3d tiles. If not set, then the last
            color in the first configured statistic will be used, or white
            if no colors are configured.

        Returns
        -------
        dict
            The metacatui configuration object as a dict.
        """

        min_z = self.get_min_z()
        try:
            top_tree_tile = self.tiles.get_filenames_from_dir("3dtiles", z=min_z)
            if len(top_tree_tile) == 0 or len(top_tree_tile) > 1:
                raise ValueError("No 3dtiles found")
        except ValueError:
            raise ValueError(
                "The top-most json node for the Cesium 3D tileset tree"
                " could noat be found. Please check that the 3dtiles"
                " dir is correctly configured, and that the workflow"
                "has already run."
            )
        top_tree_tile = top_tree_tile[0]
        # remove the 3dtiles base dir
        top_tree_tile = top_tree_tile.replace(self.get("dir_3dtiles"), "")
        # Add the hosting base url
        top_tree_tile = os.path.join(base_url, top_tree_tile)

        if color is None:
            pals = self.get_colors()
            if pals and len(pals) > 0:
                color = pals[0][-1]
            else:
                color = "white"
        color = self.to_hex(color)

        return {
            "label": "3D Tiles",
            "type": "Cesium3DTileset",
            "cesiumOptions": {
                "url": top_tree_tile,
            },
            "colorPalette": {
                "paletteType": "categorical",
                "colors": [{"color": color}],
            },
        }

    def get_metacatui_configs(self, base_url="", tile3d_color=None):
        """
        Return a dictionary that can be used to configure a layer in a
        MetacatUI Cesium map.

        Parameters
        ----------
        base_url : str
            The url to where the layers will be hosted. If not set then,
            paths will be relative starting with the TMS ID.
        3dtile_color : str
            The color to use for the 3d tiles. If not set, then the first
            color in the first configured statistic will be used, or white
            if no colors are configured.

        Returns
        -------
        list
            A list of metacatui configuration objects as dicts, starting
            with the 3D tiles layer, followed by the raster layers.
        """

        tiles3d_config = self.get_metacatui_3dtiles_config(
            base_url=base_url, color=tile3d_color
        )
        raster_configs = self.get_metacatui_raster_configs(base_url=base_url)
        return [tiles3d_config] + raster_configs

    def get_value_range(self, stat=None, z=None, sub_general=False):
        """
        Get the value range for a statistic at a particular z level. If no
        z level is specified or if there is no value range set for the
        given z level, the general value range for the statistic (at all
        z-levels) is returned.

        Parameters
        ----------
        stat : str
            The statistic name.
        z : int
            The z level.
        sub_general : bool
            When the value range for the given z-level doesn't exist,
            whether or not to substitute it with the general value range.
            If False, None is returned when the value range doesn't exist.
            If True, the general value range is returned if the value range
            for the given z-level doesn't exist.
        Returns
        -------
        tuple or None
            The value range, or None if there is no value range set.
        """
        stat_config = self.get_stat_config(stat)
        if stat_config is None:
            raise ValueError("Statistic not found: {}".format(stat))

        z_config = stat_config.get("z_config")
        general_val_range = stat_config.get("val_range")

        if z is None:
            return general_val_range
        # check if z is a string, convert if not
        if not isinstance(z, str):
            z = str(z)
        if z_config is None or z_config.get(z) is None:
            if sub_general:
                return general_val_range
            else:
                return None
        return z_config[z].get("val_range")

    def create_value_range(self, stat=None, z=None, overwrite=False):
        """
        Create a value range for a statistic at a particular z level and
        return it. If no z level is specified, a general value range for
        the statistic will be created. If the value range already exists
        and overwrite is False, the existing value range will be returned.

        Parameters
        ----------
        stat : str
            The statistic name.
        z : int
            The z level.
        overwrite : bool
            Whether to overwrite an existing value range if it exists.
            Default is False.

        Returns
        -------
        list
            The value range.
        """
        stat_config = self.get_stat_config(stat)
        if z is None:
            val_range = stat_config.get("val_range")
            if val_range is None or overwrite:
                val_range = stat_config["val_range"] = [None, None]
            return val_range
        z_config = stat_config.get("z_config")
        if z_config is None:
            z_config = stat_config["z_config"] = {}
        if z_config.get(z) is None:
            z_config[z] = {}
        val_range = z_config[z].get("val_range")
        if val_range is None or overwrite:
            val_range = z_config[z]["val_range"] = [None, None]
        return val_range

    def get_min(self, stat=None, z=None, sub_general=False):
        """
        Get the minimum value for a statistic at a particular z level. If
        no z level is specified, the general minimum value for the
        statistic (at all z-levels) is returned.

        Parameters
        ----------
        stat : str
            The statistic name.
        z : int
            The z level.
        sub_general : bool
            When the min for the given z-level doesn't exist, whether or
            not to substitute it with the general min for the statistic. If
            False, None is returned when the min doesn't exist. If True,
            the general min is returned if the min for the given z-level
            doesn't exist. Default is False.

        Returns
        -------
        float or None
            The minimum value, or None if there is no minimum value set.
        """
        value_range = self.get_value_range(stat, z, sub_general)
        if value_range is None:
            return None
        min_val = value_range[0]
        if min_val is None and sub_general:
            min_val = self.get_value_range(stat, None)[0]
        return min_val

    def get_max(self, stat=None, z=None, sub_general=False):
        """
        Get the maximum value for a statistic at a particular z level. If
        no z level is specified, the general maximum value for the
        statistic (at all z-levels) is returned.

        Parameters
        ----------
        statistic : str
            The statistic name.
        z : int
            The z level.
        sub_general : bool
            When the max for the given z-level doesn't exist, whether or
            not to substitute it with the general max for the statistic. If
            False, None is returned when the max doesn't exist. If True,
            the general max is returned if the max for the given z-level
            doesn't exist. Default is False.

        Returns
        -------
        float or None
            The maximum value, or None if there is no maximum value set.
        """
        value_range = self.get_value_range(stat, z, sub_general)
        if value_range is None:
            return None
        max_val = value_range[1]
        if max_val is None and sub_general:
            max_val = self.get_value_range(stat, None)[1]
        return max_val

    def set_min(self, value, stat=None, z=None):
        """
        Set the minimum value for a statistic at a particular z level. If
        no z level is specified, the general minimum value for the
        statistic (at all z-levels) is set.

        Parameters
        ----------
        value : float
            The minimum value.
        stat : str
            The statistic name.
        z : int
            The z level.
        """
        # Since overwrite is false, if the value range already exists, this
        # will return it
        value_range = self.create_value_range(stat, z)
        value_range[0] = value

    def set_max(self, value, stat=None, z=None):
        """
        Set the maximum value for a statistic at a particular z level. If
        no z level is specified, the general maximum value for the
        statistic (at all z-levels) is set.

        Parameters
        ----------
        value : float
            The maximum value.
        stat : str
            The statistic name.
        z : int
            The z level.
        """
        # Since overwrite is false, if the value range already exists, this
        # will return it
        value_range = self.create_value_range(stat, z)
        value_range[1] = value

    def max_missing(self, stat, z, sub_general=False):
        """
        Whether the maximum value for a statistic at a particular z level
        is missing. A maximum value is missing if no value is set for the
        given z-level and statistic. If sub_general is True, then the
        maximum value is missing only if there is also not a maximum value
        set for the statistic (independently of the z-level).

        Parameters
        ----------
        stat : str
            The statistic name.
        z : int
            The z level.
        sub_general : bool
            When the max for the given z-level doesn't exist, whether or
            not substituting with the general max for that stat is allowed.

        Returns
        -------
        bool
            Whether the maximum value is missing.
        """
        value_range = self.get_value_range(stat, z, sub_general)
        if value_range is None:
            return True
        return value_range[1] is None

    def min_missing(self, stat, z, sub_general=False):
        """
        Whether the minimum value for a statistic at a particular z level
        is missing. A minimum value is missing if no value is set for the
        given z-level and statistic. If sub_general is True, then the
        minimum value is missing only if there is also not a minimum value
        set for the statistic (independently of the z-level).

        Parameters
        ----------
        stat : str
            The statistic name.
        z : int
            The z level.
        sub_general : bool
            When the min for the given z-level doesn't exist, whether or
            not substituting with the general min for that stat is allowed.

        Returns
        -------
        bool
            Whether the minimum value is missing.
        """
        value_range = self.get_value_range(stat, z, sub_general)
        if value_range is None:
            return True
        return value_range[0] is None

    def get_raster_config(self):
        """
        Return a list of options to pass to the Raster.from_vector method
        in the pdgraster (viz-raster) package. Example of returned config
        looks like:
        {
            'centroid_properties': ('staging_centroid_x',
                'staging_centroid_y'),
            'shape': (256, 256),
            'stats': [
                {
                    'name': 'polygon_count',
                    'weight_by': 'count',
                    'property': 'polygon_count',
                    'aggregation_method':'sum'
                }, {
                    'name': 'coverage',
                    'weight_by': 'area',
                    'property': 'grid_area_prop',
                    'aggregation_method': 'sum'
                }
            ]
        }

        Returns
        -------
        dict
            A dictionary containing the configuration for shape,
            centroid_properties, and stats for Raster.from_vector method.
        """

        cent_x = self.polygon_prop("centroid_x")
        cent_y = self.polygon_prop("centroid_y")

        stats_config_keys = ("name", "weight_by", "property", "aggregation_method")
        stats_config = []
        for stat_config in self.config["statistics"]:
            stats_config.append({k: stat_config[k] for k in stats_config_keys})

        raster_config = {
            "centroid_properties": (cent_x, cent_y),
            "shape": self.get("tile_size"),
            "stats": stats_config,
        }

        return raster_config

    def get_path_manager_config(self):
        """
        Return a config formated for the TilePathManager class

        Returns
        -------
        dict
            A dict containing the configuration for the Tile Path Manager
            class. Example:
                {
                    'tms_id: 'WGS1984Quad',
                    'path_structure': ['style', 'tms', 'z', 'x', 'y'],
                    'base_dirs': {
                        'geotiff': {
                            'path': 'path/to/geotiff/dir',
                            'ext': '.tif'
                        },
                        'web_tiles': {
                            'path': 'path/to/web_tiles/dir',
                            'ext': '.png'
                        }
                    }
        """
        return {
            "tms_id": self.get("tms_id"),
            "path_structure": self.get("tile_path_structure"),
            "base_dirs": {
                "input": {"path": self.get("dir_input"), "ext": self.get("ext_input")},
                "footprints": {
                    "path": self.get("dir_footprints"),
                    "ext": self.get("ext_footprints"),
                },
                "staged": {
                    "path": self.get("dir_staged"),
                    "ext": self.get("ext_staged"),
                },
                "geotiff": {"path": self.get("dir_geotiff"), "ext": ".tif"},
                "web_tiles": {
                    "path": self.get("dir_web_tiles"),
                    "ext": self.get("ext_web_tiles"),
                },
                "3dtiles": {"path": self.get("dir_3dtiles"), "ext": ".json"},
            },
        }

    def get_deduplication_config(self, gdf=None):
        """
        Return input options for the pdgstaging.deduplication method

        Parameters
        ----------
        gdf : geopandas.GeoDataFrame
            The GeoDataFrame to deduplicate. This is required if the
            deduplication method has been set to 'footprints'. The GDF is
            used to identify which footprint files to open and how to rank
            them.
        """
        method = self.get("deduplicate_method")
        file_prop = self.polygon_prop("filename")
        if method == "neighbor":
            return {
                "split_by": file_prop,
                "prop_area": self.polygon_prop("area"),
                "prop_centroid_x": self.polygon_prop("centroid_x"),
                "prop_centroid_y": self.polygon_prop("centroid_y"),
                "keep_rules": self.get("deduplicate_keep_rules"),
                "overlap_tolerance": self.get("deduplicate_overlap_tolerance"),
                "overlap_both": self.get("deduplicate_overlap_both"),
                "centroid_tolerance": self.get("deduplicate_centroid_tolerance"),
                "distance_crs": self.get("deduplicate_distance_crs"),
                "return_intersections": False,  # not used at the moment, need to re-introduce this feature since removed dict step when labeling duplicates
                "prop_duplicated": self.polygon_prop("duplicated"),
            }
        if method == "footprints":
            files = gdf[file_prop].unique().tolist()
            footprints = {}

            for f in files:
                try:
                    footprints[f] = self.footprint_path_from_input(f, check_exists=True)
                except FileNotFoundError:
                    logger.warning(
                        f"No footprint files found for file {f}. "
                        "Deduplication will not be performed for this file."
                    )
            return {
                "split_by": file_prop,
                "footprints": footprints,
                "keep_rules": self.get("deduplicate_keep_rules"),
                "prop_duplicated": self.polygon_prop("duplicated"),
            }

        return None

    def deduplicate_at(self, step):
        """
        Check whether deduplication should occur at a given step in the
        pipeline

        Parameters
        ----------
        step : 'staging' or 'raster' or '3dtiles'
            The step name.

        Returns
        -------
        bool
            Whether deduplication should occur at the given step.
        """
        dedup = self.get("deduplicate_at")
        if isinstance(dedup, list) and step in dedup:
            return True
        else:
            return False

    def get_deduplication_method(self):
        """
        Return the deduplication method set in the config.

        Returns
        -------
        str
            The name of the deduplication method function,
            which can be assigned to a new variable and executed as the
            deduplciation function.
        """
        method = self.get("deduplicate_method")
        if method == "neighbor" or method == "footprints":
            return method
        return None

    def footprint_path_from_input(self, path, check_exists=False):
        """
        Get the footprint path from an input path

        Parameters
        ----------
        path : str
            The path to the input file.
        check_exists : bool, optional
            Whether to check if the file exists. Defaults to False. If True,
            will raise a FileNotFoundError if the file does not exist.

        Returns
        -------
        path : str
            The path to the footprint file.
        """

        dir_input = self.get("dir_input").strip(os.sep)
        dir_footprints = self.get("dir_footprints")
        ext_footprints = self.get("ext_footprints")
        # Ensure the path doesn't contian the input dir or any leading slashes
        path = path.strip(os.sep).removeprefix(dir_input).strip(os.sep)
        # Remove extension from path
        path = os.path.splitext(path)[0]
        path = os.path.join(dir_footprints, path + ext_footprints)
        if check_exists:
            if os.path.exists(path):
                logger.info(f"Successfully found footprint file: {path}")
                return path
            else:
                logger.info(f"Failed to find footprint file: {path}")
                raise FileNotFoundError(path)
        else:
            return path

    def update_ranges(self, new_ranges, save_config=True):
        """
        Update the value ranges for the statistics, only if there is a min
        or max missing for a given z-level. A min or max is deemed to be
        missing if there is not one set for the stat-z-level combination,
        and there is not a general value set for the stat (independently of
        z).

        Parameters
        ----------
        new_ranges : dict
            A dict of new value ranges for z-level within each statistic.
            Example:
                {
                    'polygon_count': {
                        '0': (0.8, None), '1': (0, 5),
                } ...

        save_config : bool
            Whether to save the updated config to the config file.
        """
        for stat, zs in new_ranges.items():
            for z, val_range in zs.items():
                if self.min_missing(stat, z, True):
                    self.set_min(val_range[0], stat, z)
                if self.max_missing(stat, z, True):
                    self.set_max(val_range[1], stat, z)

        if save_config:
            self.write(updated=True)

    def list_updates(self):
        """
        Compare what has changed between the original config and the
        updated config

        Returns
        -------
        list
            A list of strings describing what has changed.
        """
        current_config = self.config
        original_config = self.original_config
        updates = []

        # which keys have changed
        for key in current_config:
            curr_val = current_config[key]
            old_val = original_config[key]
            if key not in original_config:
                updates.append(f"{key} added")
            elif curr_val != old_val:
                # if the value is a dict, compare the keys
                if isinstance(curr_val, dict):
                    for subkey in curr_val:
                        if subkey not in old_val:
                            updates.append(f"{key}->{subkey} added")
                        elif curr_val[subkey] != old_val[subkey]:
                            updates.append(
                                f"{key}->{subkey} changed from "
                                f"{old_val[subkey]} to "
                                f"{curr_val[subkey]}"
                            )
                else:
                    updates.append(f"{key} changed from {old_val} to " f"{curr_val}")

        # which keys have been removed
        for key in original_config:
            if key not in current_config:
                updates.append(f"{key} removed")

        return updates

    @staticmethod
    def to_hex(color_str):
        """
        Convert a color string to a hex string without alpha channel
        """
        color = Color(color_str).convert("sRGB").mask("alpha")
        hex_str = color.to_string(hex=True)
        if len(hex_str) == 9:
            hex_str = hex_str[:-2]
        return hex_str

    @staticmethod
    def color_list_from_cmaps(cmap_name):
        """
        Get a list of colors from a colormaps colormap

        Parameters
        ----------
        cmap_name : str
            The name of the colormaps colormap.

        Returns
        -------
        list
            A list of colors as hex codes, no longer than 10 colors.
        """
        cmap = getattr(cmaps, cmap_name)
        pal_len = 10 if cmap.N > 10 else cmap.N
        rgb_vals = (cmap.discrete(pal_len).colors * 255).astype(int).tolist()
        rgb_hex = [f"#{i:02x}{j:02x}{k:02x}" for i, j, k in rgb_vals]
        return rgb_hex
