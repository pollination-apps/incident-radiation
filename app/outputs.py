"""Functions for processing outputs."""
import os
import pathlib
import streamlit as st

from ladybug_geometry.geometry3d import Point3D, Plane
from ladybug.color import Colorset
from ladybug.legend import LegendParameters
from ladybug.datatype.energyintensity import Radiation
from ladybug.datatype.energyflux import Irradiance
from ladybug_display.visualization import VisualizationData, AnalysisGeometry, \
    ContextGeometry, VisualizationSet
from honeybee.units import conversion_factor_to_meters
from ladybug_vtk.visualization_set import VisualizationSet as VTKVisualizationSet

from pollination_streamlit_io import send_results
from pollination_streamlit_viewer import viewer


def report_total_radiation(rad_values, container, avg_irr, unit_conv=1):
    """Report the total radiation across all of the simulation geometry."""
    face_areas = st.session_state.simulation_geo.face_areas
    total = 0
    for rad, area in zip(rad_values, face_areas):
        total += rad * area * unit_conv
    if avg_irr:
        tot_area = sum(face_areas) * unit_conv
        container.header('Average Irradiance: {:,.1f} W/m2'.format(total / tot_area))
    else:
        container.header('Total Radiation: {:,.0f} kWh'.format(total))


def display_results(host, target_folder, user_id, rad_values, avg_irr, container):
    """Create the visualization of the radiation results.

    Args:
        host: Text for the host of the app.
        target_folder: Text for the target folder out of which the simulation will run.
        user_id: A unique user ID for the session, which will be used to ensure
            other simulations do not overwrite this one.
        rad_values: A list of radiation values to be visualized.
        avg_irr: Boolean to note wether rad values are radiation in kWh/m2 instead
            of irradiance in W/m2.
        container: The streamlit container to which the viewer will be added.
    """
    # create the visualization set object with the results if there are values
    if rad_values:
        d_type = Irradiance('Incident Irradiance') if avg_irr \
            else Radiation('Incident Radiation')
        unit = 'W/m2' if avg_irr else 'kWh/m2'
        if st.session_state.override_min_max:
            min_val = st.session_state.legend_min
            max_val = st.session_state.legend_max
        elif st.session_state.use_benefit:
            extrema = max(abs(min(rad_values)), max(rad_values))
            min_val, max_val = -extrema, extrema
        else:
            min_val, max_val = min(rad_values), max(rad_values)
        color_set = reversed(Colorset.benefit_harm()) \
            if st.session_state.use_benefit else Colorset.original()
        l_par = LegendParameters(
            min=min_val, max=max_val, title=unit,
            segment_count=st.session_state.legend_seg_count,
            base_plane=Plane(o=Point3D(10, 50, 0)))
        l_par.decimal_count = 1
        l_par.colors = color_set
        viz_data = VisualizationData(
            rad_values, l_par, data_type=d_type, unit=unit)
        a_geo = AnalysisGeometry(
            'Analysis_Geometry', [st.session_state.simulation_geo], [viz_data])
        viz_set = VisualizationSet('Radiation_Study', [a_geo])

    # send the results to the CAD environment if applicable
    in_ap_display = False
    if host in ('rhino', 'sketchup', 'revit'):
        ap_dis_help = 'Check to have the results display through a viewer in the ' \
            'application instead of being pushed to the CAD environment.'
        in_ap_display = container.checkbox(
            label='Display Results in App', value=False, help=ap_dis_help)
        options = {
            'add': True,
            'delete': host == 'revit',
            'preview': False,
            'clear': False,
            'subscribe-preview': True
        }
        if not rad_values or in_ap_display:
            with container:
                send_results(results=[], key='rad-grids',
                             option='subscribe-preview', options=options)
        else:
            with container:
                send_results(results=viz_set.to_dict(), key='rad-grids',
                             option='subscribe-preview', options=options)
                u_conv = conversion_factor_to_meters(st.session_state.unit_system) ** 2
                report_total_radiation(rad_values, container, avg_irr, u_conv)

    # draw the VTK visualization
    if host == 'web' or in_ap_display:  # write the radiation values to files
        if not rad_values:
            return
        # if the visualization set is displaying in the viewer, add the context
        if st.session_state.context_geo is not None:
            geo_obj = []
            for face3d in st.session_state.context_geo:
                for seg in face3d.boundary_segments:
                    geo_obj.append(seg)
                if face3d.has_holes:
                    for hole in face3d.hole_segments:
                        geo_obj.extend(hole)
            con_geo = ContextGeometry('ContextShade', geo_obj)
            con_geo.display_name = 'Context Shade'
            viz_set.add_geometry(con_geo)
        # report the total radiation (or average irradiance)
        hb_model = st.session_state.hb_model
        unit_conv = conversion_factor_to_meters(hb_model.units) ** 2 \
            if hb_model is not None else \
            conversion_factor_to_meters(st.session_state.unit_system) ** 2
        report_total_radiation(rad_values, container, avg_irr, unit_conv)
        # display the results in the 3D viewer
        if st.session_state.vtk_path is None:
            result_folder = os.path.join(target_folder, 'data', user_id)
            if not os.path.isdir(result_folder):
                os.makedirs(result_folder)
            vtk_vs = VTKVisualizationSet.from_visualization_set(viz_set)
            st.session_state.vtk_path = vtk_vs.to_vtkjs(
                folder=result_folder, name='vis_set')
        vtk_path = st.session_state.vtk_path
        with container:
            viewer(content=pathlib.Path(vtk_path).read_bytes(), key='vtk_res_model')
