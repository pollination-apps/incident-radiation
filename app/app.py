"""Pollination Incident Radiation App."""
import streamlit as st
from pollination_streamlit_io import get_host

from inputs import initialize, get_inputs
from simulation import run_simulation
from outputs import display_results


st.set_page_config(
    page_title='Incident Radiation',
    page_icon='https://github.com/ladybug-tools/artwork/raw/master/icons_components'
    '/ladybug/png/incidentrad.png',
    initial_sidebar_state='collapsed',
)  # type: ignore
st.sidebar.image(
    'https://uploads-ssl.webflow.com/6035339e9bb6445b8e5f77d7/616da00b76225ec0e4d975ba'
    '_pollination_brandmark-p-500.png',
    use_column_width=True
)


def main(platform):
    """Perform the main calculation of the App."""
    # title
    st.header('Incident Radiation')
    st.markdown("""---""")  # horizontal divider line between title and input

    # initialize the app and load up all of the inputs
    initialize()
    in_container = st.container()  # container to hold the inputs
    get_inputs(platform, in_container)
    st.markdown("""---""")  # horizontal divider line between input and output

    # run the simulation
    offset_distance = 0.1 if platform in ('rhino', 'sketchup') else 0
    context_geo = []
    if st.session_state.sim_context_geo is not None:
        context_geo.extend(st.session_state.sim_context_geo)
    if st.session_state.context_geo is not None:
        context_geo.extend(st.session_state.context_geo)
    run_simulation(
        st.session_state.target_folder, st.session_state.user_id,
        st.session_state.sky_file_path, st.session_state.run_period,
        st.session_state.high_sky_density, st.session_state.average_irradiance,
        st.session_state.use_benefit, st.session_state.balance_temperature,
        st.session_state.simulation_geo, context_geo, offset_distance,
        st.session_state.ground_reflectance, st.session_state.north
    )

    # load the results
    out_container = st.container()  # container to hold the results
    display_results(
        platform, st.session_state.target_folder, st.session_state.user_id,
        st.session_state.radiation_values, st.session_state.average_irradiance,
        out_container
    )


if __name__ == '__main__':
    # get the platform from the query uri
    query = st.experimental_get_query_params()
    platform = get_host() or 'web'
    main(platform)
