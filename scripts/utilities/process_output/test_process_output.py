#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: djackson
"""
import os
import yaml

workingDir = "C:/Users/admin/Documents/QEDA/DWR/programs/dsm2/dsm2/src/ptm/scripts/utilities/process_output"
os.chdir(workingDir)

from process_output import ProcessOutput

p = ProcessOutput()

# Test survival output processing
configFile = os.path.join(workingDir, "example_process_output_config.yaml")

# Read YAML configuration file
with open(configFile) as fH:
    config = yaml.safe_load(fH)

if config["createFluxDat"]:
    p.createFluxDat(config["fluxOutputDir"], config["fluxFiles"], config["fluxSimLoc"], config["fluxDatLocs"], config["fluxDatDays"])

if config["createSurvDat"]:
    p.createSurvDat(config["survOutputDir"], config["survFiles"], config["survDatLocs"])

if  config["processSurvival"]:
    p.processSurvival(config["survivalFile"])

if config["echoConfig"]:
    p.printConfig(config["echoConfigNetCDF"])

