"""Run a ray tracing simulation with Radiance and compute incident radiation."""
import math
import streamlit as st

from ladybug.viewsphere import view_sphere
from ladybug_radiance.skymatrix import SkyMatrix
from ladybug_radiance.intersection import intersection_matrix


def compute_sky_matrix(
        sky_file_path, run_period, north, high_sky_density, ground_reflectance,
        avg_irr, use_benefit, bal_temp):
    """Compute the sky matrix from an input weather file and run period."""
    # create the sky matrix from the files
    hoys = None if len(run_period) == 8760 else run_period.hoys
    if sky_file_path.name.endswith('.epw'):
        if use_benefit:
            sky_matrix = SkyMatrix.from_epw_benefit(
                str(sky_file_path), bal_temp, 2, hoys,
                north, high_sky_density, ground_reflectance)
        else:
            sky_matrix = SkyMatrix.from_epw(
                str(sky_file_path), hoys, north, high_sky_density, ground_reflectance)
    elif sky_file_path.name.endswith('.stat'):
        sky_matrix = SkyMatrix.from_stat(
            str(sky_file_path), hoys, north, high_sky_density, ground_reflectance)
    else:
        msg = 'Unrecognized file: {}.\nMust have an .epw extension or ' \
            'a .stat extension.'.format(sky_file_path)
        raise ValueError(msg)
    # get the direct and diffuse radiation values
    dir_vals, diff_vals = sky_matrix.direct_values, sky_matrix.diffuse_values
    if avg_irr:  # compute the radiation values into irradiance
        conversion = 1000 / sky_matrix.wea_duration
        dir_vals = tuple(v * conversion for v in dir_vals)
        diff_vals = tuple(v * conversion for v in diff_vals)
    # return the session state variable for the sky sphere values
    total_sky_rad = [dir_rad + dif_rad for dir_rad, dif_rad in zip(dir_vals, diff_vals)]
    ground_value = (sum(total_sky_rad) / len(total_sky_rad)) * ground_reflectance
    ground_rad = [ground_value] * len(total_sky_rad)
    return total_sky_rad + ground_rad


def compute_intersection_matrix(
        study_mesh, context_geo, offset_dist, north, high_res):
    """Compute the intersection matrix between the points of a study_mesh and sky dome.
    """
    # process the sky into an acceptable format
    lb_vecs = view_sphere.reinhart_dome_vectors if high_res \
        else view_sphere.tregenza_dome_vectors
    if north != 0:
        north_angle = math.radians(north)
        lb_vecs = tuple(vec.rotate_xy(north_angle) for vec in lb_vecs)
    lb_grnd_vecs = tuple(vec.reverse() for vec in lb_vecs)
    vectors = lb_vecs + lb_grnd_vecs
    # compute the intersection matrix
    return intersection_matrix(
        vectors, study_mesh.face_centroids, study_mesh.face_normals, context_geo,
        offset_dist, True)


def run_simulation(
    target_folder, user_id, sky_file_path, run_period, high_sky_density, avg_irr,
    use_benefit, bal_temp, study_mesh, context_geo, offset_dist,
    ground_reflectance, north
):
    """Run a simulation to get incident radiation."""
    button_holder = st.empty()
    run_help = 'Check to have the radiation calculation automatically re-run every ' \
        'time one of the inputs is changed. This option should only be used for ' \
        'simpler models where the simulation time is relatively fast.'
    auto_rerun = st.checkbox(label='Automatic Re-run', value=False, help=run_help)
    # check to be sure there is a model
    if not sky_file_path or not study_mesh or not context_geo or \
            st.session_state.radiation_values is not None:
        return

    # simulate the model if the button is pressed
    if auto_rerun or button_holder.button('Compute Radiation'):
        # get the values for the radiation of the view sphere
        if st.session_state.sky_matrix is None:
            st.session_state.sky_matrix = compute_sky_matrix(
                sky_file_path, run_period, north, high_sky_density, ground_reflectance,
                avg_irr, use_benefit, bal_temp)
        sky_mtx = st.session_state.sky_matrix

        # get the intersection matrix if it does not already exist
        if st.session_state.intersection_matrix is None:
            high_res = False if len(sky_mtx) == 290 else True
            st.session_state.intersection_matrix = compute_intersection_matrix(
                study_mesh, context_geo, offset_dist, north, high_res)
        int_mtx = st.session_state.intersection_matrix

        # multiply the sky matrix by the intersection matrix
        st.session_state.radiation_values = [
            sum(r * w for r, w in zip(pt_rel, sky_mtx))
            for pt_rel in int_mtx
        ]
        button_holder.write('')
