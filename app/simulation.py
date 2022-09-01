"""Run a ray tracing simulation with Radiance and compute incident radiation."""
import os
import subprocess
import math

import streamlit as st

from ladybug_geometry.geometry3d import Face3D, Mesh3D
from ladybug.futil import write_to_file_by_name
from ladybug.viewsphere import view_sphere
from ladybug.wea import Wea
from ladybug.epw import EPW
from honeybee_radiance_command.oconv import Oconv
from honeybee_radiance_command.rcontrib import Rcontrib, RcontribOptions
from honeybee_radiance_command._command_util import run_command
from honeybee_radiance.geometry.polygon import Polygon
from honeybee_radiance.geometry.source import Source
from honeybee_radiance.modifier.material.light import Light
from honeybee_radiance.lib.modifiers import black
from honeybee_radiance.config import folders as rad_folders


# constants for converting RGB values output by gendaymtx to broadband radiation
PATCHES_PER_ROW = {
    1: view_sphere.TREGENZA_PATCHES_PER_ROW + (1,),
    2: view_sphere.REINHART_PATCHES_PER_ROW + (1,)
}
PATCH_ROW_COEFF = {
    1: view_sphere.TREGENZA_COEFFICIENTS,
    2: view_sphere.REINHART_COEFFICIENTS
}
assert rad_folders.radbin_path is not None, 'Failed to find the Radiance installation.'
gendaymtx_exe = os.path.join(rad_folders.radbin_path, 'gendaymtx.exe') if \
    os.name == 'nt' else os.path.join(rad_folders.radbin_path, 'gendaymtx')


def broadband_radiation(patch_row_str, row_number, wea_duration, sky_density=1):
    """Parse a row of gendaymtx RGB patch data in W/sr/m2 to radiation in kWh/m2.

    This includes applying broadband weighting to the RGB bands, multiplication
    by the steradians of each patch, and multiplying by the duration of time that
    they sky matrix represents in hours.

    Args:
        patch_row_str: Text string for a single row of RGB patch data.
        row_number: Integer for the row number that the patch corresponds to.
        sky_density: Integer (either 1 or 2) for the density.
        wea_duration: Number for the duration of the Wea in hours. This is used
            to convert between the average value output by the command and the
            cumulative value that is needed for all ladybug analyses.
    """
    R, G, B = patch_row_str.split(b' ')
    weight_val = 0.265074126 * float(R) + 0.670114631 * float(G) + 0.064811243 * float(B)
    return weight_val * PATCH_ROW_COEFF[sky_density][row_number] * wea_duration


def parse_mtx_data(data_str, wea_duration, sky_density=1):
    """Parse a string of Radiance gendaymtx data to a list of radiation-per-patch.

    This function handles the removing of the header and the conversion of the
    RGB irradiance-per-steradian values to broadband radiation. It also removes
    the first patch, which is the ground and is not used by Ladybug.

    Args:
        data_str: The string that has been output by gendaymtx to stdout.
        wea_duration: Number for the duration of the Wea in hours. This is used
            to convert between the average value output by the command and the
            cumulative value that is needed for all ladybug analyses.
        sky_density: Integer (either 1 or 2) for the density.
    """
    # split lines and remove the header, ground patch and last line break
    data_lines = data_str.split(b'\n')
    patch_lines = data_lines[9:-1]

    # loop through the rows and convert the radiation RGB values
    broadband_irr = []
    patch_counter = 0
    for i, row_patch_count in enumerate(PATCHES_PER_ROW[sky_density]):
        row_slice = patch_lines[patch_counter:patch_counter + row_patch_count]
        irr_vals = (broadband_radiation(row, i, wea_duration, sky_density)
                    for row in row_slice)
        broadband_irr.extend(irr_vals)
        patch_counter += row_patch_count
    return broadband_irr


def run_gendaymtx(wea_file, wea_duration, density):
    """Run a Wea file through gendaymtx and get direct and diffuse radiation."""
    use_shell = True if os.name == 'nt' else False
    # command for direct patches
    cmds1 = [gendaymtx_exe, '-m', str(density), '-d', '-O1', '-A', wea_file]
    process = subprocess.Popen(cmds1, stdout=subprocess.PIPE, shell=use_shell)
    stdout = process.communicate()
    dir_data_str = stdout[0]
    # command for diffuse patches
    cmds2 = [gendaymtx_exe, '-m', str(density), '-s', '-O1', '-A', wea_file]
    process = subprocess.Popen(cmds2, stdout=subprocess.PIPE, shell=use_shell)
    stdout = process.communicate()
    diff_data_str = stdout[0]
    # parse the data into a single matrix
    dir_vals = parse_mtx_data(dir_data_str, wea_duration, density)
    diff_vals = parse_mtx_data(diff_data_str, wea_duration, density)
    return dir_vals, diff_vals


def split_for_benefit(sky_file_path, use_benefit, bal_temp):
    """Split an input EPW file into two Wea files for radiation benefit/harm."""
    dir_vals1, dif_vals1, dir_vals2, dif_vals2 = [], [], [], []
    epw_obj = EPW(sky_file_path.as_posix())
    zip_obj = zip(
        epw_obj.direct_normal_radiation,
        epw_obj.diffuse_horizontal_radiation,
        epw_obj.dry_bulb_temperature
    )
    for dir_v, dif_v, temp in zip_obj:
        if temp < bal_temp - 2:
            dir_vals1.append(dir_v)
            dif_vals1.append(dif_v)
            dir_vals2.append(0)
            dif_vals2.append(0)
        elif temp > bal_temp + 2:
            dir_vals2.append(dir_v)
            dif_vals2.append(dif_v)
            dir_vals1.append(0)
            dif_vals1.append(0)
        else:
            dir_vals1.append(0)
            dif_vals1.append(0)
            dir_vals2.append(0)
            dif_vals2.append(0)
    wea_obj1 = Wea.from_annual_values(epw_obj.location, dir_vals1, dif_vals1)
    wea_obj2 = Wea.from_annual_values(epw_obj.location, dir_vals2, dif_vals2)
    return wea_obj1, wea_obj2


def compute_sky_matrix(sky_file_path, run_period, high_sky_density, avg_irr,
                       use_benefit, bal_temp):
    """Compute the sky matrix from an input weather file and run period."""
    # create a Wea file from the weather file
    density = 2 if high_sky_density else 1
    wea_obj2 = None
    if sky_file_path.name.endswith('.epw'):
        wea_file = sky_file_path.as_posix().replace('.epw', '.wea')
        if use_benefit:
            wea_obj, wea_obj2 = split_for_benefit(sky_file_path, use_benefit, bal_temp)
        else:
            wea_obj = Wea.from_epw_file(sky_file_path.as_posix())
    elif sky_file_path.name.endswith('.stat'):
        wea_file = sky_file_path.as_posix().replace('.stat', '.wea')
        wea_obj = Wea.from_stat_file(sky_file_path.as_posix())
    # apply the run period to the Wea
    if len(run_period) != 8760:
        wea_obj = wea_obj.filter_by_analysis_period(run_period)
        if wea_obj2 is not None:
            wea_obj2 = wea_obj2.filter_by_analysis_period(run_period)
        wea_duration = len(run_period)
    else:
        wea_duration = 8760
    wea_duration = 1 if avg_irr else wea_duration / 1000  # 1000 converts to kWh
    wea_obj.write(wea_file)

    # execute the Radiance gendaymtx command
    dir_vals, diff_vals = run_gendaymtx(wea_file, wea_duration, density)

    # if there's a second wea, then use it to compute radiation harm
    if wea_obj2 is not None:
        wea_file2 = '{}_harm.wea'.format(wea_file.replace('.wea', ''))
        wea_obj2.write(wea_file2)
        dir_vals2, diff_vals2 = run_gendaymtx(wea_file2, wea_duration, density)
        dir_vals = [db - dh for db, dh in zip(dir_vals, dir_vals2)]
        diff_vals = [db - dh for db, dh in zip(diff_vals, diff_vals2)]

    # set the session state variables
    mtx_data = (dir_vals, diff_vals)
    st.session_state.sky_matrix = mtx_data


def compute_intersection_matrix(
        sim_folder, study_mesh, context_geo, offset_dist, north, high_res):
    """Compute the intersection matrix between the points of a study_mesh and sky dome.
    """
    # process the input geometry and vectors into an acceptable format
    if offset_dist != 0:
        points = [pt.move(vec * offset_dist) for pt, vec in
                  zip(study_mesh.face_centroids, study_mesh.face_normals)]
    else:
        points = study_mesh.face_centroids
    lb_vecs = view_sphere.reinhart_dome_vectors if high_res \
        else view_sphere.tregenza_dome_vectors
    if north != 0:
        north_angle = math.radians(north)
        lb_vecs = tuple(vec.rotate_xy(north_angle) for vec in lb_vecs)
    lb_grnd_vecs = tuple(vec.reverse() for vec in lb_vecs)
    vectors = lb_vecs + lb_grnd_vecs

    # write the geometry to .rad files
    geo_strs = [black.to_radiance(minimal=True, include_modifier=False)]
    for i, geo in enumerate(context_geo):
        if isinstance(geo, Face3D):
            verts = tuple(pt.to_array() for pt in geo.vertices)
            poly = Polygon('poly_{}'.format(i), verts, black)
            geo_strs.append(poly.to_radiance(minimal=True, include_modifier=False))
        elif isinstance(geo, Mesh3D):
            for fi, f_geo in enumerate(geo.face_vertices):
                verts = tuple(pt.to_array() for pt in f_geo)
                poly = Polygon('poly_{}_{}'.format(i, fi), verts, black)
                geo_strs.append(poly.to_radiance(minimal=True, include_modifier=False))
    scene_file = 'geometry.rad'
    write_to_file_by_name(sim_folder, scene_file, '\n'.join(geo_strs))

    # write the vectors to a file
    vec_modifier = Light('vec_light', 1, 1, 1)
    vec_strs, vec_mods = [], []
    for i, vec in enumerate(vectors):
        vec_id = 'vec_light{}'.format(i)
        vec_mods.append(vec_id)
        vec_modifier.identifier = vec_id
        source = Source('vec_{}'.format(i), vec.to_array(), modifier=vec_modifier)
        vec_strs.append(source.to_radiance(minimal=True))
    vec_file, vec_mod_file = 'vectors.rad', 'vectors.mod'
    write_to_file_by_name(sim_folder, vec_file, '\n'.join(vec_strs))
    write_to_file_by_name(sim_folder, vec_mod_file, '\n'.join(vec_mods))

    # create the .pts file
    sensors = []
    for pt, vec in zip(points, study_mesh.face_normals):
        sen_str = '%s %s' % (' '.join(str(v) for v in pt), ' '.join(str(v) for v in vec))
        sensors.append(sen_str)
    pts_file = 'sensors.pts'
    write_to_file_by_name(sim_folder, pts_file, '\n'.join(sensors))

    # create the octree
    env = None
    if rad_folders.env != {}:
        env = rad_folders.env
    env = dict(os.environ, **env) if env else None
    scene_oct = 'scene.oct'
    oconv = Oconv(inputs=[vec_file, scene_file], output=scene_oct)
    oconv.run(env, cwd=sim_folder)

    # run the ray tracing command
    output_mtx = 'results.mtx'
    options = RcontribOptions()
    cpu_count = os.cpu_count()
    cpu_count = 1 if cpu_count is None or cpu_count <= 1 else cpu_count - 1
    rad_par = '-V- -aa 0.0 -y {} -I -faf -ab 0 -dc 1.0 -dt 0.0 -dj 0.0 -dr 0 ' \
        '-n {}'.format(len(points), cpu_count)
    options.update_from_string(rad_par)
    options.M = '"{}"'.format(os.path.join(os.path.abspath(sim_folder), vec_mod_file))
    rcontrib = Rcontrib(options=options, octree=scene_oct, sensors=pts_file)
    cmd = rcontrib.to_radiance().replace('\\', '/')
    cmd = '{} | rmtxop -fa - -c 14713 0 0 | getinfo -  > {}'.format(cmd, output_mtx)
    run_command(cmd, env=env, cwd=sim_folder)

    # load the intersection matrix
    int_mtx = []
    with open(os.path.join(sim_folder, output_mtx), 'r') as rf:
        for row in rf:
            int_mtx.append([float(v) for v in row.split()])
    st.session_state.intersection_matrix = int_mtx


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
            compute_sky_matrix(sky_file_path, run_period, high_sky_density,
                               avg_irr, use_benefit, bal_temp)
        mtx = st.session_state.sky_matrix
        total_sky_rad = [dir_rad + dif_rad for dir_rad, dif_rad in zip(mtx[0], mtx[1])]
        ground_value = (sum(total_sky_rad) / len(total_sky_rad)) * ground_reflectance
        ground_rad = [ground_value] * len(total_sky_rad)
        all_rad = total_sky_rad + ground_rad

        # get the intersection matrix if it does not already exist
        if st.session_state.intersection_matrix is None:
            high_res = False if len(total_sky_rad) == 145 else True
            sim_folder = os.path.join(target_folder, 'data', user_id)
            compute_intersection_matrix(
                sim_folder, study_mesh, context_geo, offset_dist, north, high_res)

        # multiply the sky matrix by the intersection matrix
        st.session_state.radiation_values = [
            sum(r * w for r, w in zip(pt_rel, all_rad))
            for pt_rel in st.session_state.intersection_matrix
        ]
        button_holder.write('')
