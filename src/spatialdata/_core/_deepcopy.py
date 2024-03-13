from __future__ import annotations

from copy import deepcopy as _deepcopy
from functools import singledispatch

from anndata import AnnData
from dask.array.core import Array as DaskArray
from dask.dataframe.core import DataFrame as DaskDataFrame
from geopandas import GeoDataFrame
from multiscale_spatial_image import MultiscaleSpatialImage
from spatial_image import SpatialImage

from spatialdata._core.spatialdata import SpatialData
from spatialdata._utils import multiscale_spatial_image_from_data_tree
from spatialdata.models._utils import SpatialElement
from spatialdata.models.models import PointsModel, RasterSchema, get_model


@singledispatch
def deepcopy(element: SpatialData | SpatialElement) -> SpatialData | SpatialElement:
    """
    Deepcopy a SpatialData or SpatialElement object.

    Deepcopy will load the data in memory. Using this function for large Dask-backed objects is discouraged. In that
    case, please save the SpatialData object to a different disk location and read it back again.

    Parameters
    ----------
    element
        The SpatialData or SpatialElement object to deepcopy

    Returns
    -------
    A deepcopy of the SpatialData or SpatialElement object
    """
    raise RuntimeError(f"Wrong type for deepcopy: {type(element)}")


# In the implementations below, when the data is loaded from Dask, we first use compute() and then we deepcopy the data.
# This leads to double copying the data, but since we expect the data to be small, this is acceptable.
@deepcopy.register(SpatialData)
def _(sdata: SpatialData) -> SpatialData:
    elements_dict = {}
    for _, element_name, element in sdata.gen_elements():
        elements_dict[element_name] = deepcopy(element)
    return SpatialData.from_elements_dict(elements_dict)


@deepcopy.register(SpatialImage)
def _(element: SpatialImage) -> SpatialImage:
    model = get_model(element)
    if isinstance(element.data, DaskArray):
        element = element.compute()
    return model.parse(element.copy(deep=True))


@deepcopy.register(MultiscaleSpatialImage)
def _(element: MultiscaleSpatialImage) -> MultiscaleSpatialImage:
    raise NotImplementedError(
        "Deepcopy of MultiscaleSpatialImage is deferred until the support of "
        "multiscale_spatial_image 1.0.0 is added."
    )
    model = get_model(element)
    for key in element:
        ds = element[key].ds
        assert len(ds) == 1
        variable = ds.__iter__().__next__()
        if isinstance(element[key][variable].data, DaskArray):
            element[key][variable] = element[key][variable].compute()
    msi = multiscale_spatial_image_from_data_tree(element.copy(deep=True))
    assert isinstance(model, RasterSchema)
    model.validate(msi)
    return msi


@deepcopy.register(GeoDataFrame)
def _(gdf: GeoDataFrame) -> GeoDataFrame:
    new_gdf = _deepcopy(gdf)
    # temporary fix for https://github.com/scverse/spatialdata/issues/286.
    new_attrs = _deepcopy(gdf.attrs)
    new_gdf.attrs = new_attrs
    return new_gdf


@deepcopy.register(DaskDataFrame)
def _(df: DaskDataFrame) -> DaskDataFrame:
    return PointsModel.parse(df.compute().copy(deep=True))


@deepcopy.register(AnnData)
def _(adata: AnnData) -> AnnData:
    return _deepcopy(adata)
