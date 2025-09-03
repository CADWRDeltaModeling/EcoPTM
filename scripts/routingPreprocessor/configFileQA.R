# Script to verify the ECO-PTM config file, including that the station locations are valid for the specified tide file.
# Doug Jackson
# doug@QEDAconsulting.com

# Need yaml to read the config file. At this point, .libPaths() may still point to the default library,
# so it may use a version of yaml that's different from the one in the conda environment, but that's probably OK.
library(yaml)
####################################################################################################
# Constants
####################################################################################################
args <- commandArgs(trailingOnly=T)
if(length(args)==0) {
    cat("Reading hard-coded path to configuration file.\n")
    configFile <- "C:/Users/admin/Documents/QEDA/DWR/programs/EcoPTM_private/scripts/routingPreprocessor/config_preprocessors.yaml"
    workingDir <- "C:/Users/admin/Documents/QEDA/DWR/programs/EcoPTM_private/scripts/routingPreprocessor"
} else {
    cat("Reading path to configuration file as a command line argument\n")
    configFile <- args[1]
    workingDir <- getwd()
}
cat("Reading configuration from ", configFile, "\n")
config <- read_yaml(configFile)$configFileQA

####################################################################################################
# Install packages that aren't available through conda
####################################################################################################
cat("=========================================================\n")
cat("Running configFileQA.R\n")
cat("---------------------------------------------------------\n")
cat("Installing packages that are not available through conda.\n")
if(config$runInCondaEnv) {
    # Use the library associated with the active R installation as the default.
    # This ensures that R is using packages installed in the current conda environment.
    .libPaths(R.home("library"))
}

# Check if rhdf5 is installed. If not, install it.
if(!require("rhdf5", quietly=T)) {
    cat("Installing rhdf5...\n")
    options(install.packages.compile.from.source="always")
    install.packages("BiocManager", repos="http://cran.us.r-project.org", quiet=T)
    BiocManager::install("rhdf5")
}

library(rhdf5)
library(tidyverse)
####################################################################################################
# Functions
####################################################################################################
# Load variables from config file after verifying they exist
loadVar <- function(varName) {
    if(is.null(config[[varName]])) {
        stop(paste(varName, "not found in configuration file."))
    }
    else {return (config[[varName]])}
}

####################################################################################################
# Run
####################################################################################################
cat("---------------------------------------------------------\n")
cat("workingDir: ", workingDir, "\n")
setwd(workingDir)

outputDir <- file.path(workingDir, "output")
dir.create(outputDir, showWarnings=F, recursive=T)

tideFile <- loadVar("tideFile")
configFile <- loadVar("configFile")

configECOPTM <- suppressWarnings(read_yaml(configFile))
survGroups <- configECOPTM$survival_groups

# Assemble start and end stations
stationsList <- list()
for(i in 1:length(survGroups)) {
    thisSurvGroup <- survGroups[[i]]
    
    for(j in 1:length(length(thisSurvGroup$start_stations))) {
        thisStartStation <- thisSurvGroup$start_stations[[j]]
        
        thisChan <- as.character(thisStartStation[[1]])
        thisDist <- thisStartStation[[2]]
        
        thisStation <- data.frame(chan=thisChan, dist=thisDist)
        stationsList[[length(stationsList)+1]] <- thisStation
    }
    
    for(j in 1:length(thisSurvGroup$end_stations)) {
        thisEndStation <- thisSurvGroup$end_stations[[j]]
        
        thisChan <- as.character(thisEndStation[[1]])
        thisDist <- thisEndStation[[2]]
        
        thisStation <- data.frame(chan=thisChan, dist=thisDist)
        stationsList[[length(stationsList)+1]] <- thisStation
    }
}

stations <- bind_rows(stationsList)

# Remove duplicates and drop stations with non-numeric channels
stations <- stations %>% distinct() %>% arrange(chan, dist)
stations <- suppressWarnings(stations %>% mutate(chan=as.numeric(chan)))
stations <- stations %>% filter(!is.na(chan))

# Read channel information
h5f <- H5Fopen(tideFile)

cat("Reading channel information.\n")
channelH <- h5f&'hydro/input/channel'
channel <- channelH[]

h5closeAll()

channel <- channel %>% select(chan_no, length) %>% rename(chan=chan_no)

stations <- left_join(stations, channel, by=c("chan"))

stations <- stations %>% mutate(distNotOK=dist>length)

cat("---------------------------------------------------------\n")
cat("tide file: ", tideFile, "\n")
cat("ECO-PTM config file: ", configFile, "\n")
cat("Stations\n")
print(stations)
cat("---------------------------------------------------------\n")

numDistNotOK <- sum(stations$distNotOK)
if(numDistNotOK==0) {
    cat("Passed check of station distance <= channel length.\n")
} else {
    cat("Failed check of station distance <= channel length.", numDistNotOK, " stations failed.\n")
}

cat("=========================================================\n")