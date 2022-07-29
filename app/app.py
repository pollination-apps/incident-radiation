"""Pollination Incident Radiation App."""
import streamlit as st
from pollination_streamlit_io import get_host


st.set_page_config(
    page_title='Incident Radiation',
    page_icon='https://github.com/ladybug-tools/artwork/raw/master/icons_components'
    '/honeybee/png/loadbalance.png',
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


if __name__ == '__main__':
    # get the platform from the query uri
    query = st.experimental_get_query_params()
    platform = get_host() or 'web'
    main(platform)
