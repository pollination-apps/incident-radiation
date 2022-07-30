"""Functions for processing outputs."""
import os
import json
import pathlib
import streamlit as st

from honeybee_vtk.model import Model as VTKModel, SensorGridOptions, DisplayMode
from pollination_streamlit_io import send_geometry
from pollination_streamlit_viewer import viewer


def write_result_files(res_folder, hb_model, rad_values):
    """Write the radiation results to files."""
    grids_info, st_ind = [], 0
    for grid in hb_model.properties.radiance.sensor_grids:
        grids_info.append(grid.info_dict(hb_model))
        grid_file = os.path.join(res_folder, '{}.res'.format(grid.identifier))
        with open(grid_file, 'w') as gf:
            gf.write('\n'.join(
                str(v) for v in rad_values[st_ind: st_ind + grid.count]))
        st_ind += grid.count
    grids_info_file = os.path.join(res_folder, 'grids_info.json')
    with open(grids_info_file, 'w', encoding='utf-8') as fp:
        json.dump(grids_info, fp, indent=2, ensure_ascii=False)


def get_vtk_config(res_folder: pathlib.Path, values) -> str:
    """Write Incident Radiation config to a folder."""
    cfg = {
        "data": [
            {
                "identifier": "Incident Radiation",
                "object_type": "grid",
                "unit": "kWh/m2",
                "path": res_folder.as_posix(),
                "hide": False,
                "legend_parameters": {
                    "hide_legend": False,
                    "color_set": "original",
                    "min": min(values),
                    "max": max(values),
                    "label_parameters": {
                        "color": [34, 247, 10],
                        "size": 0,
                        "bold": True
                    }
                }
            }
        ]
    }
    config_file = res_folder.parent.joinpath('config.json')
    config_file.write_text(json.dumps(cfg))
    return config_file.as_posix()


def get_vtk_model_result(simulation_folder: pathlib.Path, cfg_file, hb_model, container):
    """Get the viewer with radiation results"""
    hbjson_path = hb_model.to_hbjson(hb_model.identifier, simulation_folder)
    vtk_model = VTKModel.from_hbjson(hbjson_path, SensorGridOptions.Mesh)
    vtk_result_path = vtk_model.to_vtkjs(
        folder=simulation_folder.resolve(),
        config=cfg_file,
        model_display_mode=DisplayMode.Wireframe,
        name=hb_model.identifier)
    st.session_state.vtk_path = vtk_result_path


def display_results(host, target_folder, user_id, rad_values, container):
    """Create the visualization of the radiation results.

    Args:
        host: Text for the host of the app.
        target_folder: Text for the target folder out of which the simulation will run.
        user_id: A unique user ID for the session, which will be used to ensure
            other simulations do not overwrite this one.
        rad_values: A list of radiation values to be visualized.
        container: The streamlit container to which the viewer will be added.
    """
    if host in ('rhino', 'sketchup'):  # pass the results to the CAD environment
        options = {
            'add': True,
            'delete': False,
            'preview': False,
            'clear': False,
            'subscribe-preview': True
        }
        if not rad_values:
            with container:
                send_geometry(geometry=[], key='rad-grids',
                              option='subscribe-preview', options=options)
        else:
            analytical_mesh = {
                "type": "AnalyticalMesh",
                "mesh": [st.session_state.simulation_geo.to_dict()],
                "values": rad_values
            }
            with container:
                send_geometry(geometry=analytical_mesh, key='rad-grids',
                              option='subscribe-preview', options=options)
    else:  # write the radiation values to files
        if not rad_values:
            return
        # set up the result folders
        res_folder = os.path.join(target_folder, 'data', user_id, 'results')
        if not os.path.isdir(res_folder):
            os.mkdir(res_folder)
        res_path = pathlib.Path(res_folder).resolve()
        if st.session_state.vtk_path is None:
            hb_model = st.session_state.hb_model
            write_result_files(res_folder, hb_model, rad_values)
            cfg_file = get_vtk_config(res_path, rad_values)
            get_vtk_model_result(res_path.parent, cfg_file, hb_model, container)
        vtk_path = st.session_state.vtk_path
        with container:
            viewer(content=pathlib.Path(vtk_path).read_bytes(), key='vtk_res_model')
