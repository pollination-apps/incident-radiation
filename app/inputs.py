"""Functions for initializing inputs and formatting them for simulation"""
import uuid
import json
from pathlib import Path

import streamlit as st

from ladybug_geometry.geometry3d import Face3D, Mesh3D, Polyface3D
from ladybug.analysisperiod import AnalysisPeriod
from honeybee.model import Model

from pollination_streamlit_io import get_hbjson, get_geometry, manage_settings

GRID_SIZES = {
    'Meters': (1.0, 0.25),
    'Millimeters': (1000.0, 250.0),
    'Feet': (3.0, 1.0),
    'Inches': (36.0, 12.0),
    'Centimeters': (100.0, 25.0)
}


def initialize():
    """Initialize any of the session state variables if they don't already exist."""
    # user session
    if 'user_id' not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())[:8]
    if 'target_folder' not in st.session_state:
        st.session_state.target_folder = Path(__file__).parent
    # sky sim session
    if 'sky_file_path' not in st.session_state:
        st.session_state.sky_file_path = None
    if 'north' not in st.session_state:
        st.session_state.north = 0
    if 'high_sky_density' not in st.session_state:
        st.session_state.high_sky_density = False
    if 'average_irradiance' not in st.session_state:
        st.session_state.average_irradiance = False
    if 'use_benefit' not in st.session_state:
        st.session_state.use_benefit = False
    if 'balance_temperature' not in st.session_state:
        st.session_state.balance_temperature = 16.0
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
    if 'offset_distance' not in st.session_state:  # used only in rhino and sketchup
        st.session_state.offset_distance = 0
    if 'unit_system' not in st.session_state:  # used only in rhino and sketchup
        st.session_state.unit_system = 'Meters'
    if 'intersection_matrix' not in st.session_state:
        st.session_state.intersection_matrix = None
    # output session
    if 'override_min_max' not in st.session_state:
        st.session_state.override_min_max = False
    if 'legend_min' not in st.session_state:
        st.session_state.legend_min = 0.0
    if 'legend_max' not in st.session_state:
        st.session_state.legend_max = 100.0
    if 'legend_seg_count' not in st.session_state:
        st.session_state.legend_seg_count = 11
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
    weather_file = st.session_state.weather_data
    if weather_file:
        # save EPW in data folder
        epw_path = Path(
            f'./{st.session_state.target_folder}/data/'
            f'{st.session_state.user_id}/{weather_file.name}'
        )
        epw_path.parent.mkdir(parents=True, exist_ok=True)
        epw_path.write_bytes(weather_file.read())
        st.session_state.sky_file_path = epw_path
    else:
        st.session_state.sky_file_path = None


def get_sky_file(column):
    """Get the sky matrix from the EPW App input."""
    # upload weather file
    msg = 'Select an EPW or STAT weather file to be used in the simulation.\n' \
        'STAT files will generate a clear sky from monthly optical depths.'
    column.file_uploader(
        'Weather file (EPW or STAT)', type=['epw', 'stat'],
        on_change=new_sky_file, key='weather_data', help=msg
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
        geo_meshes = [sg.mesh for sg in hb_model.properties.radiance.sensor_grids
                      if sg.mesh is not None]
        if len(geo_meshes) == 0:
            raise ValueError(
                'Model contains no sensor grids with meshes. '
                'Sensor grids with meshes are required to use this app.')
        st.session_state.simulation_geo = Mesh3D.join_meshes(geo_meshes)
        st.session_state.context_geo = \
            [obj.punched_geometry for obj in hb_model.faces] + \
            [obj.geometry for obj in hb_model.shades]


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
    st.session_state.vtk_path = None
    # load the model object from the file data
    if st.session_state['geometry_data'] is not None and \
            'geometry' in st.session_state['geometry_data']:
        geo_data = st.session_state['geometry_data']['geometry']
        if geo_data is None:
            st.session_state.simulation_geo = None
            return
        grid_size = st.session_state.grid_size
        geo_meshes, geo_face3d = [], []
        for geo in geo_data:
            if isinstance(geo, (list, tuple)):
                for geo_dict in geo:
                    if geo_dict['type'] == 'Face3D':
                        face = Face3D.from_dict(geo_dict)
                        geo_face3d.append(face)
                        try:
                            geo_meshes.append(face.mesh_grid(grid_size))
                        except AssertionError:
                            pass  # grid size is not small enough
            elif geo_dict['type'] == 'Mesh3D':
                mesh = Mesh3D.from_dict(geo_dict)
                geo_meshes.append(mesh)
                geo_face3d.append(mesh)
            elif geo_dict['type'] == 'Polyface3D':
                polyface = Polyface3D.from_dict(geo_dict)
                for face in polyface.faces:
                    geo_face3d.append(face)
                    try:
                        geo_meshes.append(face.mesh_grid(grid_size))
                    except AssertionError:
                        pass  # grid size is not small enough
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
    first_try = 'geo_options' not in st.session_state
    with column:
        if first_try:
            options = {
                'subscribe': {'show': True, 'selected': False},
                'selection': {'show': True, 'selected': True}
            }
            geometry_data = get_geometry(
                key='geometry_data', on_change=new_geometry,
                options=options, label='Geometry')
            st.session_state.geo_options = True
        else:
            geometry_data = get_geometry(
                key='geometry_data', on_change=new_geometry, label='Geometry')
    if st.session_state.simulation_geo is None and geometry_data is not None \
            and 'geometry' in geometry_data:
        new_geometry()


def new_context():
    """Process a newly-loaded context geometry."""
    # reset the simulation results and get the file data
    st.session_state.intersection_matrix = None
    st.session_state.radiation_values = None
    st.session_state.vtk_path = None
    # load the model object from the file data
    if 'geometry' in st.session_state['context_data']:
        geo_data = st.session_state['context_data']['geometry']
        if geo_data is None:
            st.session_state.simulation_geo = None
            return
        geo_objs = []
        for geo in geo_data:
            if isinstance(geo, (list, tuple)):
                for geo_dict in geo:
                    if geo_dict['type'] == 'Face3D':
                        face = Face3D.from_dict(geo_dict)
                        geo_objs.append(face)
            elif geo['type'] == 'Mesh3D':
                mesh = Mesh3D.from_dict(geo)
                geo_objs.append(mesh)
            elif geo['type'] == 'Polyface3D':
                polyface = Polyface3D.from_dict(geo)
                for face in polyface.faces:
                    geo_objs.append(face)
        st.session_state.context_geo = geo_objs


def get_context_geometry(column):
    """Get the context Geometry from the CAD environment."""
    # load the model object from the file data
    first_try = 'context_options' not in st.session_state
    with column:
        if first_try:
            options = {
                'subscribe': {'show': True, 'selected': False},
                'selection': {'show': True, 'selected': True}
            }
            context_data = get_geometry(
                key='context_data', on_change=new_context,
                options=options, label='Context')
            st.session_state.context_options = True
        else:
            context_data = get_geometry(
                key='context_data', on_change=new_context, label='Context')
    if st.session_state.context_geo is None and context_data is not None \
            and 'geometry' in context_data:
        new_context()


def get_run_period(container):
    """Get a run period from user input."""
    pit_help = 'Check to have the radiation calculation run for only a single '\
        'hour of the year.'
    with container.form(key='Run Period'):
        if container.checkbox(label='Point In Time', value=False, help=pit_help):
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
        # sense the units of the CAD environment
        settings_dict = manage_settings(key='default_settings', settings={})
        if settings_dict is not None:
            if isinstance(settings_dict, str):
                settings_dict = json.loads(settings_dict)
            st.session_state.unit_system = settings_dict['units']
            g_size, g_step = GRID_SIZES[st.session_state.unit_system]
        else:
            g_size, g_step = GRID_SIZES['Meters']
        # create an input component for the grid size
        grid_help = 'Number in model units for the size of grid cells at which ' \
            'the input Geometry will be subdivided. The smaller the grid size, ' \
            'the higher the resolution and the longer the calculation will take.'
        in_grid_size = m_col_last.number_input(
            label='Grid Size', min_value=0.001,
            value=g_size, step=g_step, help=grid_help)
        if in_grid_size != st.session_state.grid_size:
            st.session_state.grid_size = in_grid_size
            new_geometry()
        # create an input component for the offset distance
        off_help = 'Number in model units for the distance to move points from ' \
            'the surfaces of the input geometry.'
        in_off_dist = m_col_last.number_input(
            label='Offset Distance', min_value=0.001,
            value=g_size, step=g_step, help=off_help)
        if in_off_dist != st.session_state.offset_distance:
            st.session_state.offset_distance = in_off_dist
            st.session_state.intersection_matrix = None
            st.session_state.radiation_values = None
            st.session_state.vtk_path = None
        # add buttons to get the geometry and context
        get_study_geometry(m_col_1)
        get_context_geometry(m_col_2)
    else:
        m_col_1, m_col_last = container.columns([2, 1])
        get_model(m_col_1)

    # get the input ground reflectance
    ref_help = 'Number between 0 and 1 for the average ground reflectance. This is ' \
        'used to build an emissive ground hemisphere that influences points with an ' \
        'unobstructed view to the ground.'
    in_g_ref = m_col_last.number_input(
        label='Ground Reflectance', min_value=0.0, max_value=1.0, value=0.2,
        step=0.05, help=ref_help)
    if in_g_ref != st.session_state.ground_reflectance:
        st.session_state.ground_reflectance = in_g_ref
        new_sky_matrix()

    # get the input file to generate the sky
    w_col_1, w_col_2 = container.columns([2, 1])
    get_sky_file(w_col_1)

    # set up inputs for sky density, north and type of output metric
    north_help = 'Number between -360 and 360 for the counterclockwise difference ' \
        'between the North and the positive Y-axis in degrees. 90 is West; 270 is East.'
    in_north = w_col_2.number_input(
        label='North', min_value=-360, max_value=360, value=0, help=north_help)
    if in_north != st.session_state.north:
        st.session_state.north = in_north
        st.session_state.intersection_matrix = None
        st.session_state.radiation_values = None  # reset to have results recomputed
        st.session_state.vtk_path = None  # reset to have results recomputed
    den_help = 'Check to use a higher-density Reinhart sky matrix, which has ' \
        'roughly 4 times the sky patches as the default Tregenza sky. ' \
        'Note that, while the Reinhart sky has a higher resolution and is ' \
        'more accurate, it will result in considerably longer calculation time.'
    sky_density = w_col_2.checkbox(label='High Density Sky', value=False, help=den_help)
    if sky_density != st.session_state.high_sky_density:
        st.session_state.high_sky_density = sky_density
        new_sky_matrix()
        st.session_state.intersection_matrix = None
    irr_help = 'Check to display the radiation results in units of average irradiance ' \
        '(W/m2) over the time period instead of units of cumulative radiation (kWh/m2).'
    avg_irradiance = w_col_2.checkbox(
        label='Average Irradiance', value=False, help=irr_help)
    if avg_irradiance != st.session_state.average_irradiance:
        st.session_state.average_irradiance = avg_irradiance
        new_sky_matrix()
    sf_path = st.session_state.sky_file_path
    if sf_path and sf_path.name.endswith('.epw'):
        ben_help = 'Check to run a radiation benefit study that weighs helpful ' \
            'wintertime radiation against harmful summertime radiation. This ' \
            'option is only available when the uploaded file is an EPW.'
        use_benefit = w_col_2.checkbox(
            label='Radiation Benefit', value=False, help=ben_help)
        if use_benefit != st.session_state.use_benefit:
            st.session_state.use_benefit = use_benefit
            new_sky_matrix()
            st.session_state.intersection_matrix = None
        if use_benefit:
            bal_help = 'Number for the balance temperature in (C) around which ' \
                'radiation switches from being helpful to harmful. Hours where the '\
                'temperature is below this will contribute positively to the benefit ' \
                '(eg. passive solar heating) while hours above this temperature will ' \
                'contribute negatively (eg. increased cooling load). This should ' \
                'usually be the balance temperature of the building being studied.'
            in_bal_temp = w_col_2.number_input(
                label='Balance Temperature (C)', min_value=2.0, max_value=26.0,
                value=16.0, step=1.0, help=bal_help)
            if in_bal_temp != st.session_state.balance_temperature:
                st.session_state.balance_temperature = in_bal_temp
                new_sky_matrix()
                st.session_state.intersection_matrix = None

    # set up the inputs for the date range
    container.markdown("""---""")  # horizontal divider between datetimes and others
    in_run_period = get_run_period(container)
    if in_run_period != st.session_state.run_period:
        st.session_state.run_period = in_run_period
        new_sky_matrix()
        st.session_state.vtk_path = None  # reset to have results recomputed

    # set up the side panel inputs to customize the legend
    over_min_max = st.sidebar.checkbox(
        label='Override Min and Max', value=False)
    if over_min_max != st.session_state.override_min_max:
        st.session_state.override_min_max = over_min_max
        new_sky_matrix()
    disable_min_max = False if over_min_max else True
    in_leg_min = st.sidebar.number_input(
        label='Legend Min', value=0.0, step=10.0, disabled=disable_min_max)
    if in_leg_min != st.session_state.legend_min:
        st.session_state.legend_min = in_leg_min
        new_sky_matrix()
    in_leg_max = st.sidebar.number_input(
        label='Legend Max', value=100.0, step=10.0, disabled=disable_min_max)
    if in_leg_max != st.session_state.legend_max:
        st.session_state.legend_max = in_leg_max
        new_sky_matrix()
    in_seg_count = st.sidebar.number_input(
        label='Legend Segments', value=11, step=1)
    if in_seg_count != st.session_state.legend_seg_count:
        st.session_state.legend_seg_count = in_seg_count
        new_sky_matrix()
