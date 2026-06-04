#!usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to create a YAML config file from a CSV file containing a subset of the config variables
"""
__author__ = "Doug Jackson, QEDA Consulting, LLC"
__email__ = "doug@QEDAconsulting.com"

import os
import re
import yaml
import pandas as pd
from datetime import datetime as dt

class CreateConfig:
    
    def __init__(self, inputFileCSV, outputDir):
        """Initialize CreateConfig object."""
        self.workingDir = os.path.dirname(os.path.realpath(__file__))
        
        self.inputFileCSV = inputFileCSV
        self.outputDir = outputDir

    def run(self):
        """Create output file."""
        os.makedirs(self.outputDir, exist_ok=True)

        # Read config file templates
        with open("ptmConfigTemplate_SouthDelta.yaml", "r") as fH:
            templateSouthDelta = fH.read()
        with open("ptmConfigTemplate_NorthDelta.yaml", "r") as fH:
            templateNorthDelta = fH.read()
        
        # Read input file
        self.inputs = pd.read_csv(self.inputFileCSV)

        self.formatInput()

        configSouthDelta = self.replacePlaceholders(templateSouthDelta)
        configNorthDelta = self.replacePlaceholders(templateNorthDelta)
        
        try:
            with open(os.path.join(self.outputDir, "ptmConfig_SouthDelta.yaml"), "w") as fH:
                print(configSouthDelta, end="", file=fH)
            print(f"Wrote config file to {os.path.join(self.outputDir, "ptmConfig_SouthDelta.yaml")}")
        except:
            print(f"Could not write config file to {os.path.join(self.outputDir, "ptmConfig_SouthDelta.yaml")}")

        try:
            with open(os.path.join(self.outputDir, "ptmConfig_NorthDelta.yaml"), "w") as fH:
                print(configNorthDelta, end="", file=fH)
            print(f"Wrote config file to {os.path.join(self.outputDir, "ptmConfig_NorthDelta.yaml")}")
        except:
            print(f"Could not write config file to {os.path.join(self.outputDir, "ptmConfig_NorthDelta.yaml")}")
    
    def formatInput(self):
        """Format input and report errors"""
        try:
            releaseDatetime = dt.strptime(self.inputs.loc[self.inputs["variable"]=="releases_release_date", "value"].values[0], "%d/%m/%Y")
            self.inputs.loc[self.inputs["variable"]=="releases_release_date", "value"] = dt.strftime(releaseDatetime, "%d/%m/%Y")
        except:
            print("-"*100)
            print("Unable to properly format releases_release_date. Use a text editor to verify that it is in d/m/Y format, e.g., 05/01/2015. ")
            print(f"Value found: {self.inputs.loc[self.inputs["variable"]=="releases_release_date", "value"].values[0]}")
            print("-"*100)

        try:
            ptmStartDate = dt.strptime(self.inputs.loc[self.inputs["variable"]=="ptm_start_date", "value"].values[0], "%d%b%Y")
            self.inputs.loc[self.inputs["variable"]=="ptm_start_date", "value"] = dt.strftime(ptmStartDate, "%d%b%Y")
        except:
            print("-"*100)
            print("Unable to properly format ptm_start_date. Use a text editor to verify that it is in %d%b%Y format, e.g., 21APR2015. ")
            print(f"Value found: {self.inputs.loc[self.inputs["variable"]=="ptm_start_date", "value"].values[0]}")
            print("-"*100)

        try:
            ptmEndDate = dt.strptime(self.inputs.loc[self.inputs["variable"]=="ptm_end_date", "value"].values[0], "%d%b%Y")
            self.inputs.loc[self.inputs["variable"]=="ptm_end_date", "value"] = dt.strftime(ptmEndDate, "%d%b%Y")
        except:
            print("-"*100)
            print("Unable to properly format ptm_end_date. Use a text editor to verify that it is in %d%b%Y format, e.g., 21APR2015. ")
            print(f"Value found: {self.inputs.loc[self.inputs["variable"]=="ptm_end_date", "value"].values[0]}")
            print("-"*100)

    def replacePlaceholders(self, template):
        """Replace placeholders in template with specified values"""
        template = self.replacePlaceholder(template, "TIDEFILE_PLACEHOLDER", "tidefile")

        template = self.replacePlaceholder(template, "RELEASE_LOC_NODEID_PLACEHOLDER", "release_loc_nodeID")
        template = self.replacePlaceholder(template, "RELEASE_LOC_CHANNELID_PLACEHOLDER", "release_loc_channelID")
        template = self.replacePlaceholder(template, "RELEASE_LOC_DISTANCE_PLACEHOLDER", "release_loc_distance")
        template = self.replacePlaceholder(template, "RELEASE_LOC_STATIONNAME_PLACEHOLDER", "release_loc_stationName")

        template = self.replacePlaceholder(template, "RELEASES_RELEASE_DATE_PLACEHOLDER", "releases_release_date")
        template = self.replacePlaceholder(template, "RELEASES_RELEASE_TIME_PLACEHOLDER", "releases_release_time")
        template = self.replacePlaceholder(template, "RELEASES_PARTICLE_NUMBER_PLACEHOLDER", "releases_particle_number")

        template = self.replacePlaceholder(template, "PTM_START_DATE_PLACEHOLDER", "ptm_start_date")
        template = self.replacePlaceholder(template, "PTM_END_DATE_PLACEHOLDER", "ptm_end_date")

        template = self.replacePlaceholder(template, "TRANS_PROBS_PATH_PLACEHOLDER", "trans_probs_path")

        return template

    def replacePlaceholder(self, template, placeholder, variable):
        """Replace single placeholder in template with specified value."""
        try:
            template = template.replace(placeholder, self.inputs.loc[self.inputs["variable"]==variable, "value"].values[0]) 
        except:
            print(f"Could not find {variable} in inputs. Leaving placeholder in output files")
        
        return template
    
if __name__=="__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Utility to create a YAML config file from a CSV file containing a subset of the config variables")
    parser.add_argument("--inputFileCSV", action="store", dest="inputFileCSV", required=True)
    parser.add_argument("--outputDir", action="store", dest="outputDir", required=True)
    
    args = parser.parse_args()

    cC = CreateConfig(args.inputFileCSV, args.outputDir)
    cC.run()
    