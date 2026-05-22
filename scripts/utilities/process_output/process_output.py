"""script to do some basic post-processing of eco-ptm outputs
"""
__author__ = "Doug Jackson, QEDA Consulting, LLC"
__email__ = "doug@qedaconsulting.com"
import os
import re
import sys
import xarray as xr
import pandas as pd
import argparse
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime as dt
from datetime import timedelta
import yaml
from pathlib import Path

class ProcessOutput:

    def __init__(self):
        """Initialize a ProcessOutput object""" 
        self.figWidth = 6
        self.figHeight = 6
    
    def verifyConfig(self, config, varList):
        """Verify that the config file contains all of the variables in varList"""
        success = True
        for v in varList:
            if v not in config:
                success = False
                print(f"Required variable {v} not found in configuration file.")

        return success

    def extractFlux(self, fluxOutputDir, fluxFiles):
        """Extract all flux time series

        Keyword arguments:
        fluxOutputDir (str) -- full path to the directory where the CSVs with time series should be saved
        fluxFiles (list) -- list of paths to the netCDF flux output files
        """ 
        print("="*80)

        # Make sure the output directory exists
        os.makedirs(fluxOutputDir, exist_ok=True)
        
        for fluxFile in fluxFiles:
            print(f"Extracting flux from {fluxFile}")
            print(f"Extracting all flux time series outputs in {fluxFile}")

            p = Path(fluxFile)
            outputFile = str(p.with_suffix(".csv"))

            ds = xr.open_dataset(fluxFile)

            nodeFlux = ds["nodeFlux"].to_pandas()
            nodeFlux.columns = [c.decode("utf8") for c in nodeFlux.columns]
            nodeFlux.index = [i.decode("utf8") for i in nodeFlux.index]
            
            nodeFlux["datetime"] = [dt.strptime(d, "%m/%d/%Y %H:%M:%S") for d in nodeFlux.index]

            thisOutputFile = outputFile.replace(".csv", "_nodeFlux.csv")
            nodeFlux.to_csv(thisOutputFile, index=False)
            print(f"Saved node flux time series to {thisOutputFile}")
            
            groupFlux = ds["groupFlux"].to_pandas()
            groupFlux.columns = [c.decode("utf8") for c in groupFlux.columns]
            groupFlux.index = [i.decode("utf8") for i in groupFlux.index]
            
            groupFlux["datetime"] = [dt.strptime(d, "%m/%d/%Y %H:%M:%S") for d in groupFlux.index]

            thisOutputFile = outputFile.replace(".csv", "_groupFlux.csv")
            groupFlux.to_csv(thisOutputFile, index=False)
            print(f"Saved group flux time series to {thisOutputFile}")
            
            ds.close()

    def createFluxDat(self, fluxOutputDir, fluxFiles, fluxSimLoc, fluxDatLocs, fluxDatDays, fluxDatTotals):
        """Create dat file of flux outputs
        
        Keyword arguments:
        fluxOutputDir (str) -- full path to the directory where the dat file should be created
        fluxFiles (list) -- list of paths to the netCDF flux output files
        fluxSimLoc (str) -- insertion location
        fluxDatLocs (list) -- list of flux locations
        fluxDatDays (list) -- list of integer days from simulation start to record flux
        fluxDatTotals (dict) -- dict containing lists of flux locations to add and subtract
        """
        # Make sure the output directory exists
        os.makedirs(fluxOutputDir, exist_ok=True)

        # Read the scenario from the first file
        try:
            ds = xr.open_dataset(fluxFiles[0])
            scenario = ds["simulation_scenario"].item().decode("utf8")
            ds.close()
        except:
            scenario = "NA"

        for days in fluxDatDays:

            print("="*80)
            print(f"Creating {days} day flux output file.")

            outputFile = os.path.join(fluxOutputDir, f"ptm_fate_results_{days}day.dat")

            with open(outputFile, "w") as fH:
                print(f"Saving flux output to {outputFile}")
                print(f"{days}-day PTM Output - {scenario}", file=fH)
                header = "SimPeriod,SimLoc"
                for loc in fluxDatLocs:
                    header+=f",{loc.upper()}"
                
                # try protects against empty fluxDatTotals
                try:
                    for t in fluxDatTotals:
                        header+=f",{t}"
                except TypeError:
                    fluxDatTotals = []

                print(header, file=fH)

            for fluxFile in fluxFiles:
                print(f"Creating {days} day *.dat flux output file using outputs in {fluxFile}")

                ds = xr.open_dataset(fluxFile)

                nodeFlux = ds["nodeFlux"].to_pandas()
                nodeFlux.columns = [c.decode("utf8") for c in nodeFlux.columns]
                nodeFlux.index = [i.decode("utf8") for i in nodeFlux.index]
                
                nodes = nodeFlux.columns
                nodeFlux["datetime"] = [dt.strptime(d, "%m/%d/%Y %H:%M:%S") for d in nodeFlux.index]
                
                groupFlux = ds["groupFlux"].to_pandas()
                groupFlux.columns = [c.decode("utf8") for c in groupFlux.columns]
                groupFlux.index = [i.decode("utf8") for i in groupFlux.index]
                
                groups = groupFlux.columns
                groupFlux["datetime"] = [dt.strptime(d, "%m/%d/%Y %H:%M:%S") for d in groupFlux.index]
                
                ds.close()

                flux = pd.merge(nodeFlux, groupFlux, on="datetime", how="outer")
                flux["datetime"] = pd.to_datetime(flux["datetime"])

                # Flux outputs include one time step before the PTM start time => use second datetime entry
                flux = flux.sort_values(by="datetime")
                startDatetime = flux.iloc[1]["datetime"]

                # Obtain the first release date
                if ds["particle_type"].item().decode("utf8").upper()=="SALMON_PARTICLE":
                    firstReleaseDate, lastReleaseDate = self.getReleaseDates(fluxFile)
                    firstReleaseDatetime = dt.strptime(firstReleaseDate, "%d%b%Y")
                else:
                    delay_days = self.getDelayDays(fluxFile)
                    firstReleaseDatetime = startDatetime + timedelta(days=delay_days)

                flux["daysFromRelease"] = [(d - firstReleaseDatetime).total_seconds()/timedelta(days=1).total_seconds() for d in flux["datetime"]]

                if flux["daysFromRelease"].max()<days:
                    self.printWarning((f"No flux data found at or after {days} days from the first release date. " + 
                                       f"The latest flux data is {int(np.floor(flux['daysFromRelease'].max()))} days after release. Skipping {fluxFile}."))
                    continue
                
                thisFlux = flux[flux["daysFromRelease"]>=days].iloc[0:1]

                with open(outputFile, "a") as fH:
                    row = f"{dt.strftime(firstReleaseDatetime, '%d%b%Y').upper()}, {fluxSimLoc}"
                    for loc in fluxDatLocs:
                        try:
                            row+=f", {thisFlux[loc.upper()].values[0]}"
                        except:
                            row+=","
                        
                    # Add totals
                    for t in fluxDatTotals:
                        thisTot = 0

                        try:
                            addLocs = fluxDatTotals[t]["add"]
                            subtractLocs = fluxDatTotals[t]["subtract"]
                        except KeyError as e:
                            self.printWarning(f"Missing entry in fluxDatTotals[{t}]: {e.args[0]}. Skipping this total calculation.")
                            continue

                        # try protects against empty lists for "add" or "subtract"
                        try:
                            for a in addLocs:
                                if a.upper() not in thisFlux:
                                    self.printWarning(f"Flux location {a.upper()} not found in output. Excluding from {t} total calculation.")
                                    continue

                                thisTot+=thisFlux[a.upper()].values[0]

                            for s in subtractLocs:
                                if s.upper() not in thisFlux:
                                    self.printWarning(f"Flux location {s.upper()} not found in output. Excluding from {t} total calculation.")
                                    continue

                                thisTot-=thisFlux[s.upper()].values[0]
                        except TypeError:
                            pass
                        
                        row+=f", {float(thisTot)}"

                    print(row, file=fH)
            print(f"Done creating {days} day flux output file.")
                
    def getDelayDays(self, outputFile):
        """Obtain minimum release delay in days"""
        ds = xr.open_dataset(outputFile)

        particleInsertion = ds["particle_insertion"].to_pandas()
        particleInsertion.columns = [c.decode("utf8") for c in particleInsertion.columns]

        delays = [d.decode("utf8") for d in particleInsertion["delay"]]

        delay_days = []
        for d in delays:
            
            m = re.search(r"\d*", d)
            if len(m.group())>0:
            
                if "DAY" in d.upper():
                    delay_days.append(int(m.group(0)))
                elif "HOUR" in d.upper():
                    delay_days.append(int(m.group(0))/24)

        try:
            minDelay = np.array(delay_days).min().item()
        except:
            sys.exit("Could not obtain release delays.")

        ds.close()

        return minDelay
        
    def getReleaseDates(self, outputFile):
        """Obtain release dates from a salmon simulation output file"""
        ds = xr.open_dataset(outputFile)

        try:
            releases = pd.DataFrame(ds["release_groups:releases"])
            releaseDates = [dt.strptime(d.decode("utf8"), "%m/%d/%Y") for d in releases[1]]
            firstReleaseDatetime = np.min(releaseDates)
            lastReleaseDatetime = np.max(releaseDates)
            firstReleaseDate = dt.strftime(firstReleaseDatetime, "%d%b%Y").upper()
            lastReleaseDate = dt.strftime(lastReleaseDatetime, "%d%b%Y").upper()
        except:
            sys.exit("Could not obtain release dates.")
        
        ds.close()

        return firstReleaseDate, lastReleaseDate

    def createSurvDat(self, survOutputDir, survFiles, survDatLocs):
        """Create dat file of survival estimates
        
        Keyword arguments:
        survOutputDir (str) -- full path to the directory where the dat file should be created
        survFiles (list) -- list of patsh to the netCDF survival output files
        survDatLocs (list) -- list of survival estimates to include
        """
        print("="*80)

        # Make sure the output directory exists
        os.makedirs(survOutputDir, exist_ok=True)

        outputFile = os.path.join(survOutputDir, "eco-ptm_survival.dat")

        with open(outputFile, "w") as fH:
            print(f"Saving survival output to {outputFile}")
            header = "ptm_start_date,first_release_date,last_release_date,scenario"
            for loc in survDatLocs:
                header+=f",{loc}"
            print(header, file=fH)

        for survFile in survFiles:
            print(f"Creating *.dat survival output file using outputs from {survFile}")

            ds = xr.open_dataset(survFile)

            try:
                startDate = ds["ptm_start_date"].item().decode("utf8")
            except:
                startDate = "NA"
            
            firstReleaseDate, lastReleaseDate = self.getReleaseDates(survFile)

            try:
                scenario = ds["simulation_scenario"].item().decode("utf8")
            except:
                scenario = "NA"

            surv = ds["surv"].to_dataframe().reset_index()
            surv["survGroup"] = [s.decode("utf8") for s in surv["survGroup"]]

            ds.close()

            with open(outputFile, "a") as fH:
                row = f"{startDate},{firstReleaseDate},{lastReleaseDate},{scenario}"
                for loc in survDatLocs:
                    try:
                        thisSurv = surv.loc[surv["survGroup"]==loc, "surv"].values[0]
                    except:
                        print(f"Could not read survival for {loc}")
                        thisSurv = "NA"
                    row+=f",{thisSurv}"
                print(row, file=fH)

    def processSurvival(self, survivalFile):
        """Process survival output

        Keyword arguments:
        survivalFile (str) -- path to the netCDF survival output file
        """
        print("="*80)
        print(f"Processing survival output in {survivalFile}")

        ds = xr.open_dataset(survivalFile)
        surv = ds["surv"].to_dataframe().reset_index()
        surv["survGroup"] = [s.decode("utf8") for s in surv["survGroup"]]

        outputPath = os.path.join(os.path.dirname(survivalFile), "surv.csv")
        surv.to_csv(outputPath, index=False)
        print(f"Saved survival to {outputPath}")

        fig, ax = plt.subplots(figsize=[self.figWidth, self.figHeight])
        ax.bar(surv["survGroup"], surv["surv"])
        ax.set_xlabel("survival group")
        ax.set_ylabel("survival fraction")
        outputPath = os.path.join(os.path.dirname(survivalFile), "surv.png")
        plt.savefig(outputPath)
        print(f"Saved survival plot to {outputPath}")

        if "survDetails" in ds:
            survDetails = ds["survDetails"].to_dataframe().reset_index()
            survDetails["survDetailsKey"] = [s.decode("utf8") for s in survDetails["survDetailsKey"]]
            survDetails["survDetails"] = [s.decode("utf8") for s in survDetails["survDetails"]]
            survDetails[["component", "variable"]] = survDetails["survDetailsKey"].str.split("-", expand=True)
            survDetails = survDetails.rename(columns={"survDetails":"value"})
            survDetails = survDetails[["component", "variable", "value"]]
            survDetails.sort_values(by=["component", "variable"], inplace=True)
            outputPath = os.path.join(os.path.dirname(survivalFile), "survDetails.csv")
            survDetails.to_csv(outputPath, index=False)
            print(f"Saved survival details to {outputPath}")

    def printConfig(self, echoConfigNetCDF):
        """Print configuration values

        Keyword arguments:
        echoConfigNetCDF (str) -- path to the netCDF echoConfig output file 
        """
        print("="*80)
        if not os.path.exists(echoConfigNetCDF):
            print(f"File {echoConfigNetCDF} does not exist. Skipping echoConfig.")
            return

        print(f"Echoing configuration values in {echoConfigNetCDF}")

        ds = xr.open_dataset(echoConfigNetCDF)
        for varName in ["tidefile", "particle_type", "time_zone", "use_new_random_seed", "travel_time_output_path",
                        "sunrise", "sunset", "random_assess", "output_path_entrainment", "trans_probs_path",
                        "output_path_flux", "survival_output_path", "simulation_start_date", "show_route_survival_detail",
                        "route_survival_output_path", "display_simulation_timestep_write_all", "flux_write_all",
                        "entrainment_write_all", "survival_write_all", "ptm_start_date", "ptm_start_time",
                        "ptm_end_date", "ptm_end_time", "ptm_time_step", "display_intvl", "ptm_ivert",
                        "ptm_itrans", "ptm_iey", "ptm_iez", "ptm_iprof", "ptm_igroup", "ptm_flux_percent", 
                        "ptm_group_percent", "ptm_flux_cumulative"]:
            self.printVal(ds, varName)
        
        # Scalars
        for varName in ["stst_threshold", "tidal_cycles_to_calculate_channel_direction", "confusion_probability_constant",
                        "max_confusion_probability", "confusion_probability_slope", "assess_probability", "stuck_threshold",
                        "dicu_filter_efficiency", "theta", "ptm_random_seed", "ptm_trans_constant", "ptm_vert_constant", 
                        "ptm_trans_a_coef", "ptm_trans_b_coef", "ptm_trans_c_coef", "ptm_num_animated"]:
            self.printScalar(ds, varName)
        
        # Arrays 
        for varName in ["travel_time", "release_groups:release_loc", "release_groups:releases", "swimming_vel",
                        "channel_groups", "channel_name_lookup", "special_behavior", "barriers", "fish_screens",
                        "survival_groups:start_stations", "survival_groups:end_stations", "survival_groups:exchangeable_start_stations",
                        "survival_groups:survival_params", "particle_flux", "individual_route_survival", "route_survival_equations",
                        "individual_reach_survival", "particle_group_output", "particle_flux_output", "groups", "io_file"]:
            print("-"*80)
            thisVar = self.decodeDF(ds[varName])
            print(thisVar)

        exitStations = [c.decode("utf8") for c in ds["exit_stations"].to_pandas()]
        print(f"exit_stations: {exitStations}")

    def printVal(self, ds, varName):
        """Read a value from the output and print it"""
        try:
            thisVal = ds[varName].item().decode("utf8")
            print(f"{varName}: {thisVal}")
        except:
            print(f"Unable to read {varName}")
    
    def printScalar(self, ds, varName):
        """Read a scalar value from the output and print it"""
        try:
            thisVal = np.double(ds[varName])
            print(f"{varName}: {thisVal}")
        except:
            print(f"Unable to read {varName}")

    def decodeDF(self, dF):
        """Decode all elements of a data frame from UTF-8"""
        dF = dF.to_pandas()
        dF.columns = [c.decode("utf8") for c in dF.columns]
        dF = dF.map(lambda x: x.decode("utf-8") if isinstance(x, bytes) else x)
        dF.reset_index(inplace=True)
        return dF
    
    def printWarning(self, message):
        """Print a warning message"""
        print("-"*80)
        print(message)
        print("-"*80)

if __name__=="__main__":
    import argparse
    import yaml 

    # Read in command line arguments
    parser = argparse.ArgumentParser(description="Script to perform basic post-processing of ECO-PTM output.")
    parser.add_argument("--configFile", action="store", dest="configFile", required=True)
    args = parser.parse_args()

    configFile = args.configFile

    # Read YAML configuration file
    print("Reading configuration file")
    try:
        with open(configFile) as fH:
            config = yaml.safe_load(fH)
    except IOError as e:
        print(f"Could not load configuration file {configFile}. Does it exist? {e}")
        sys.exit()
    except yaml.YAMLError as e:
        print(f"Error while parsing process_output configuration file: {e}")
        sys.exit()

    p = ProcessOutput()

    # Verify that required switches are in config file
    if not p.verifyConfig(config, ["createFluxDat", "createSurvDat", "processSurvival", "echoConfig", "extractFlux"]):
        print("One or more required parameters are not found in the configuration file. Aborting.")
        sys.exit()

    print("Launching processes...")
    if config["createFluxDat"]:
        if not p.verifyConfig(config, ["fluxOutputDir", "fluxFiles", "fluxSimLoc", "fluxDatLocs", "fluxDatDays", "fluxDatTotals"]):
            print("One or more parameters required for createFluxDat are not found in the configuration file. Skipping.")
        else:
            p.createFluxDat(config["fluxOutputDir"], config["fluxFiles"], config["fluxSimLoc"], config["fluxDatLocs"], 
                            config["fluxDatDays"], config["fluxDatTotals"])
    
    if config["createSurvDat"]:
        if not p.verifyConfig(config, ["survOutputDir", "survFiles", "survDatLocs"]):
            print("One or more parameters required for createSurvDat are not found in the configuration file. Skipping.")
        else:
            p.createSurvDat(config["survOutputDir"], config["survFiles"], config["survDatLocs"])

    if  config["processSurvival"]:
        if not p.verifyConfig(config, ["survivalFile"]):
            print("One or more parameters required for processSurvival are not found in the configuration file. Skipping.")
        else:
            p.processSurvival(config["survivalFile"])
    
    if config["echoConfig"]:
        if not p.verifyConfig(config, ["echoConfigNetCDF"]):
            print("One or more parameters required for echoConfig are not found in the configuration file. Skipping.")
        else:
            p.printConfig(config["echoConfigNetCDF"])
    
    if config["extractFlux"]:
        if not p. verifyConfig(config, ["fluxOutputDir", "fluxFiles"]):
            print("One or more parameters required for extractFlux are not found in the configuration file. Skipping.")
        else:
            p.extractFlux(config["fluxOutputDir"], config["fluxFiles"])