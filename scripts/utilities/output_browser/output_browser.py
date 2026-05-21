# ECO-PTM output browser
#
# Doug Jackson
# doug@QEDAconsulting.com
import streamlit as st
import xarray as xr
import pandas as pd
from datetime import datetime as dt

fluxVars = ["nodeFlux", "groupFlux"]
tableVars = ["particle_insertion", "fish_screens", "particle_group_output", "particle_flux_output", "groups",
             "io_file", "release_groups:release_loc", "release_groups:releases", 
             "survival_groups:start_stations", "survival_groups:end_stations", "survival_groups:exchangeable_start_stations",
             "survival_groups:survival_params", "individual_route_survival", "fate"]
seriesVars = ["lastStation", "surv", "survDetails"]
strVars = ["particle_type", "time_zone", "use_new_random_seed", "sunrise", "sunset", "random_assess", "ptm_start_date", "ptm_start_time",
           "ptm_end_date", "ptm_end_time", "tidefile", "travel_time_output_path", "output_path_entrainment", "trans_probs_path", "output_path_flux",
           "survival_output_path", "route_survival_output_path", "fates_output_path", "display_simulation_timestep_write_all", "flux_write_all",
           "entrainment_write_all", "survival_write_all", "ptm_ivert", "ptm_itrans", "ptm_iey", "ptm_iez", "ptm_iprof", "ptm_igroup", "ptm_flux_percent",
           "ptm_group_percent", "ptm_flux_cumulative", "position_oriented_behavior_path"]
floatVars = ["stst_threshold", "tidal_cycles_to_calculate_channel_direction", "confusion_probability_constant",
           "max_confusion_probability", "confusion_probability_slope", "assess_probability", "stuck_threshold", "dicu_filter_efficiency", "max_leakage_gate_closed",
           "theta", "ptm_random_seed", "ptm_trans_constant", "ptm_vert_constant", "ptm_trans_a_coef", "ptm_trans_b_coef", "ptm_num_animated", "ctmm_time_step_min"]

allVars = [*strVars, *floatVars, *fluxVars, *tableVars, *seriesVars]
allVars.sort()

st.set_page_config(layout="wide", page_title="ECO-PTM Output Browser")
st.title("ECO-PTM output browser")

file_path = st.text_input("Enter the full path to your netCDF file:")

if file_path:
    try:
        # Load with xarray
        ds = xr.open_dataset(file_path, engine="netcdf4")
        
        # Select variable to view
        varName = st.selectbox("Select variable to view", allVars, index=None)
        
        if varName:

            if varName in fluxVars and varName in ds:

                dat = ds[varName].to_pandas()
                dat.columns = [c.decode("utf8") for c in dat.columns]
                dat.index = [i.decode("utf8") for i in dat.index]

                st.subheader(f"Variable: {varName}")
                st.write(f"Shape: {dat.shape}")
            
                st.dataframe(dat, width="stretch")
            
            elif varName in tableVars and varName in ds:
                dat = ds[varName].to_pandas()

                try:
                    dat.columns = [c.decode("utf8") for c in dat.columns]
                except:
                    pass

                st.subheader(f"Variable: {varName}")
                st.write(f"Shape: {dat.shape}")

                # Decode all bytes to UTF-8
                dat = dat.apply(lambda col: col.apply(lambda x: x.decode('utf-8') if isinstance(x, bytes) else x))
            
                st.dataframe(dat, width="stretch")

            elif varName in seriesVars and varName in ds:
                dat = ds[varName].to_pandas().to_frame()

                st.subheader(f"Variable: {varName}")
                st.write(f"Shape: {dat.shape}")

                try:
                    dat.columns = [c.decode("utf8") for c in dat.columns]
                except:
                    pass

                try:
                    dat.index = [i.decode("utf8") for i in dat.index]
                except:
                    pass

                # Decode all bytes to UTF-8
                dat = dat.apply(lambda col: col.apply(lambda x: x.decode('utf-8') if isinstance(x, bytes) else x))
            
                st.dataframe(dat, width="stretch")
            
            elif varName in strVars and varName in ds:
                dat = ds[varName].item().decode("utf8")

                st.subheader(f"Variable: {varName}")

                try:
                    if f"{dat}".strip()=="":
                        st.text(f"{varName} not contained in this output file")
                    else:
                        st.text(dat)
                except:
                    st.text(dat)

            elif varName in floatVars and varName in ds:
                dat = ds[varName].item()

                st.subheader(f"Variable: {varName}")

                try:
                    if f"{dat}".strip()=="":
                        st.text(f"{varName} not contained in this output file")
                    else:
                        st.text(dat)
                except:
                    st.text(dat)
            
            elif varName not in ds:
                st.subheader(f"Variable: {varName}")
                st.text(f"{varName} not contained in this output file")
    
    except Exception as e:
        st.error(f"Error reading file: {e}")
