"""Functions for initializing inputs and formatting them for simulation"""
import uuid
from pathlib import Path

import streamlit as st

from ladybug_geometry.geometry3d import Face3D, Mesh3D, Polyface3D
from ladybug.analysisperiod import AnalysisPeriod
from honeybee.model import Model

from pollination_streamlit_io import get_hbjson, get_geometry


def initialize():
    """Initialize any of the session state variables if they don't already exist."""
    # user session
    if 'user_id' not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())[:8]
    if 'target_folder' not in st.session_state:
        st.session_state.target_folder = Path(__file__).parent
    # sky sim session
    if 'sky_file_path' not in st.session_state:
        st.session_state.sky_file_path = False
    if 'high_sky_density' not in st.session_state:
        st.session_state.high_sky_density = False
    if 'north' not in st.session_state:
        st.session_state.north = 0
    if 'run_period' not in st.session_state:
        st.session_state.run_period = AnalysisPeriod()
    if 'sky_matrix' not in st.session_state:
        st.session_state.sky_matrix = None
    # intersection sim session
    if 'simulation_geo' not in st.session_state:
        st.session_state.simulation_geo = None
    if 'sim_context_geo' not in st.session_state:
        st.session_state.sim_context_geo = None
    if 'context_geo' not in st.session_state:
        st.session_state.context_geo = None
    if 'hb_model' not in st.session_state:  # used only in web and revit
        st.session_state.hb_model = None
    if 'ground_reflectance' not in st.session_state:
        st.session_state.ground_reflectance = 0.2
    if 'grid_size' not in st.session_state:  # used only in rhino and sketchup
        st.session_state.grid_size = 1.0
    if 'intersection_matrix' not in st.session_state:
        st.session_state.intersection_matrix = None
    # output session
    if 'radiation_values' not in st.session_state:
        st.session_state.radiation_values = None
    if 'vtk_path' not in st.session_state:
        st.session_state.vtk_path = None


def new_sky_matrix():
    """Reset all of the state variables related to the sky matrix."""
    # reset the simulation results
    st.session_state.sky_matrix = None
    st.session_state.radiation_values = None
    st.session_state.vtk_path = None


def new_sky_file():
    """Process a newly-uploaded EPW file."""
    new_sky_matrix()
    epw_file = st.session_state.epw_data
    if epw_file:
        # save EPW in data folder
        epw_path = Path(
            f'./{st.session_state.target_folder}/data/'
            f'{st.session_state.user_id}/{epw_file.name}'
        )
        epw_path.parent.mkdir(parents=True, exist_ok=True)
        epw_path.write_bytes(epw_file.read())
        st.session_state.sky_file_path = epw_path
    else:
        st.session_state.sky_file_path = None


def get_sky_file(column):
    """Get the sky matrix from the EPW App input."""
    # upload weather file
    column.file_uploader(
        'Weather file (EPW)', type=['epw'],
        on_change=new_sky_file, key='epw_data',
        help='Select an EPW weather file to be used in the simulation.'
    )


def new_model():
    """Process a newly-uploaded Honeybee Model file."""
    # reset the simulation results and get the file data
    st.session_state.intersection_matrix = None
    st.session_state.radiation_values = None
    st.session_state.vtk_path = None
    # load the model object from the file data
    if 'hbjson' in st.session_state['hbjson_data']:
        hbjson_data = st.session_state['hbjson_data']['hbjson']
        hb_model = Model.from_dict(hbjson_data)
        st.session_state.hb_model = hb_model
        geo_meshes = [sg.mesh for sg in hb_model.properties.radiance.sensor_grids]
        st.session_state.simulation_geo = Mesh3D.join_meshes(geo_meshes)
        st.session_state.context_geo = \
            [obj.geometry for obj in hb_model.faces + hb_model.shades]


def get_model(column):
    """Get the Model input from the App input."""
    # load the model object from the file data
    with column:
        hbjson_data = get_hbjson(key='hbjson_data', on_change=new_model)
    if st.session_state.simulation_geo is None and hbjson_data is not None \
            and 'hbjson' in hbjson_data:
        new_model()


def new_geometry():
    """Process a newly-loaded geometry."""
    # reset the simulation results and get the file data
    st.session_state.intersection_matrix = None
    st.session_state.radiation_values = None
    # load the model object from the file data
    if 'geometry' in st.session_state['geometry_data']:
        geo_data = st.session_state['geometry_data']['geometry']
        grid_size = st.session_state.grid_size
        geo_meshes, geo_face3d = [], []
        for geo_dict in geo_data:
            if geo_dict['type'] == 'Polyface3D':
                polyface = Polyface3D.from_dict(geo_dict)
                for face in polyface.faces:
                    try:
                        geo_meshes.append(face.mesh_grid(grid_size))
                        geo_face3d.append(face)
                    except AssertionError:
                        pass  # grid size is not small enough
            elif geo_dict['type'] == 'Face3D':
                face = Face3D.from_dict(geo_dict)
                try:
                    geo_meshes.append(face.mesh_grid(grid_size))
                    geo_face3d.append(face)
                except AssertionError:
                    pass  # grid size is not small enough
            elif geo_dict['type'] == 'Mesh3D':
                mesh = Mesh3D.from_dict(geo_dict)
                geo_meshes.append(mesh)
                geo_face3d.append(mesh)
        if len(geo_meshes) != 0:
            st.session_state.simulation_geo = Mesh3D.join_meshes(geo_meshes)
            st.session_state.sim_context_geo = geo_face3d
        else:
            st.session_state.simulation_geo = None
            st.session_state.sim_context_geo = None
            msg = 'Failed to mesh the geometry at the specified grid size.\n' \
                'Try lowering the grid size.'
            st.write(msg)


def get_study_geometry(column):
    """Get the study Geometry from the CAD environment."""
    # load the model object from the file data
    options = {
        'subscribe': {'show': False, 'selected': False},
        'selection': {'show': True, 'selected': True}
    }
    with column:
        geometry_data = get_geometry(
            key='geometry_data', on_change=new_geometry,
            options=options, label='Get Geometry')
    if st.session_state.simulation_geo is None and geometry_data is not None \
            and 'geometry' in geometry_data:
        new_geometry()


def new_context():
    """Process a newly-loaded context geometry."""
    # reset the simulation results and get the file data
    st.session_state.intersection_matrix = None
    st.session_state.radiation_values = None
    # load the model object from the file data
    if 'geometry' in st.session_state['context_data']:
        geo_data = st.session_state['context_data']['geometry']
        geo_objs = []
        for geo_dict in geo_data:
            if geo_dict['type'] == 'Polyface3D':
                polyface = Polyface3D.from_dict(geo_dict)
                for face in polyface.faces:
                    geo_objs.append(face)
            elif geo_dict['type'] == 'Face3D':
                face = Face3D.from_dict(geo_dict)
                geo_objs.append(face)
            elif geo_dict['type'] == 'Mesh3D':
                mesh = Mesh3D.from_dict(geo_dict)
                geo_objs.append(mesh)
        st.session_state.context_geo = geo_objs


def get_context_geometry(column):
    """Get the context Geometry from the CAD environment."""
    # load the model object from the file data
    options = {
        'subscribe': {'show': False, 'selected': False},
        'selection': {'show': True, 'selected': True}
    }
    with column:
        context_data = get_geometry(
            key='context_data', on_change=new_context,
            options=options, label='Get Context')
    if st.session_state.context_geo is None and context_data is not None \
            and 'geometry' in context_data:
        new_context()


def get_run_period(container):
    """Get a run period from user input."""
    with container.form(key='Run Period'):
        if container.checkbox(label='Point In Time', value=False):
            dt_col_1, dt_col_2, dt_col_3 = container.columns(3)
            in_month = dt_col_1.number_input(
                label='Month', min_value=1, max_value=12, value=6)
            in_day = dt_col_2.number_input(
                label='Day', min_value=1, max_value=31, value=21)
            in_hour = dt_col_3.number_input(
                label='Hour', min_value=0, max_value=23, value=12)
            return AnalysisPeriod(in_month, in_day, in_hour, in_month, in_day, in_hour)
        else:
            dt_col_1, dt_col_2, dt_col_3 = container.columns(3)
            dt_col_4, dt_col_5, dt_col_6 = container.columns(3)
            st_month = dt_col_1.number_input(
                label='Start Month', min_value=1, max_value=12, value=1)
            st_day = dt_col_2.number_input(
                label='Start Day', min_value=1, max_value=31, value=1)
            st_hour = dt_col_3.number_input(
                label='Start Hour', min_value=0, max_value=23, value=0)
            end_month = dt_col_4.number_input(
                label='End Month', min_value=1, max_value=12, value=12)
            end_day = dt_col_5.number_input(
                label='End Day', min_value=1, max_value=31, value=31)
            end_hour = dt_col_6.number_input(
                label='End Hour', min_value=0, max_value=23, value=23)
            return AnalysisPeriod(st_month, st_day, st_hour,
                                  end_month, end_day, end_hour)


def get_inputs(host: str, container):
    """Get all of the inputs for the simulation."""
    # get the input geometry
    if host in ('rhino', 'sketchup'):  # get geometry and context individually
        m_col_1, m_col_2, m_col_last = container.columns(3)
        in_grid_size = m_col_last.number_input(
            label='Grid Size', min_value=0.0, value=1.0, step=1.0)
        if in_grid_size != st.session_state.grid_size:
            st.session_state.grid_size = in_grid_size
            new_geometry()
        get_study_geometry(m_col_1)
        get_context_geometry(m_col_2)
    else:
        m_col_1, m_col_last = container.columns([2, 1])
        get_model(m_col_1)

    # get the input ground reflectance
    in_g_ref = m_col_last.number_input(
        label='Ground Reflectance', min_value=0.0, max_value=1.0, value=0.2, step=0.05)
    if in_g_ref != st.session_state.ground_reflectance:
        st.session_state.ground_reflectance = in_g_ref
        st.session_state.radiation_values = None  # reset to have results recomputed
        st.session_state.vtk_path = None  # reset to have results recomputed

    # get the input file to generate the sky
    w_col_1, w_col_2 = container.columns([2, 1])
    get_sky_file(w_col_1)

    # set up inputs for sky density, north and ground reflectance
    sky_density = w_col_2.checkbox(label='High Density Sky', value=False)
    if sky_density != st.session_state.high_sky_density:
        st.session_state.high_sky_density = sky_density
        new_sky_matrix()
        st.session_state.intersection_matrix = None
    in_north = w_col_2.number_input(
        label='North', min_value=-360, max_value=360, value=0)
    if in_north != st.session_state.north:
        st.session_state.north = in_north
        st.session_state.intersection_matrix = None
        st.session_state.radiation_values = None  # reset to have results recomputed
        st.session_state.vtk_path = None  # reset to have results recomputed

    # set up the inputs for the date range
    container.markdown("""---""")  # horizontal divider between datetimes and others
    in_run_period = get_run_period(container)
    if in_run_period != st.session_state.run_period:
        st.session_state.run_period = in_run_period
        new_sky_matrix()
        st.session_state.vtk_path = None  # reset to have results recomputed
