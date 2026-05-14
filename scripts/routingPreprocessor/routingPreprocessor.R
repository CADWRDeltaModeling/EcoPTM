# Preprocessor for generating South Delta transition probabilities for the ECO-PTM using the USGS routing model.
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
    #configFile <- "C:/Users/dougj/Documents/QEDA/DWR/programs/EcoPTM_private/scripts/routingPreprocessor/config_preprocessors.yaml"
    workingDir <- "C:/Users/dougj/Documents/QEDA/DWR/programs/EcoPTM_private/scripts/routingPreprocessor"
} else {
    cat("Reading path to configuration file as a command line argument\n")
    configFile <- args[1]
    workingDir <- getwd()
}
cat("Reading configuration from ", configFile, "\n")
config <- read_yaml(configFile)$routingPreprocessor

# Number of optional command line arguments (in addition to configFile)
numOptArgs <- 4

stationLocFile <- file.path(workingDir, "stationLoc.csv")
fitHORfile <- file.path(workingDir, "fitHOR.rds")
fitTCfile <- file.path(workingDir, "fitTC.rds")
flowScalingFile <- file.path(workingDir, "flowScaling.csv")
barrierOpFile <- file.path(workingDir, "barrierOp.csv")
flowBoundsFile <- file.path(workingDir, "flowBounds.csv")

HORstationNames <- c("HOR_U", "HOR_D", "HOR_T")
TCstationNames <- c("TC_U", "TC_D", "TC_T")

# Model configuration
TClag_min <- 90
use2011 <- FALSE

# Number used to indicate missing value
missingVal <- -999

expectedSampleTime_min <- 15

####################################################################################################
# Install packages that aren't available through conda
####################################################################################################
cat("=========================================================\n")
cat("Running routingPreprocessor.R\n")
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
    install.packages("BiocManager", repos = "https://cloud.r-project.org", quiet=T)
    BiocManager::install("rhdf5")
}
if(!require("imputeTS", quietly=T)) {
    cat("Installing imputeTS...\n")
    install.packages("imputeTS", repos="http://cran.rstudio.com", quiet=T)
}
if(!require("suncalc", quietly=T)) {
    cat("Installing suncalc...\n")
    install.packages("suncalc", repos="http://cran.rstudio.com", quiet=T)
}
if(!require("tzdb", quietly=T)) {
    cat("Installing tzdb...\n")
    install.packages("tzdb", repos="http://cran.rstudio.com", quiet=T)
}

library(rhdf5)
library(tidyverse)
library(tzdb)
library(lubridate)
if(config$runInCondaEnv) {
    # lubridate may set TZDIR to the wrong location when running within a conda environment
    Sys.setenv(TZDIR=file.path(Sys.getenv("CONDA_PREFIX"), "share", "zoneinfo"))
}

library(ggplot2)
library(doParallel)
library(imputeTS)
library(slider)
library(msm)
library(suncalc)

cat("Done installing packages that are not available through conda.\n")

####################################################################################################
# Functions
####################################################################################################
# Godin filter from Mike Dodrill
# Based on code from https://github.com/ODWG/ODWGtools
smoothGodin = function(x, increment="15 mins", kind = c("mean", "max", "min")) {
    kind = match.arg(kind, c("mean", "max", "min"))
    roll_fun = switch(kind,
                      "mean" = mean,
                      "max" = max,
                      "min" = min
    )
    increment = string_to_difftime(increment)
    inc.units = units(increment)
    d25 = as.difftime(25L, units = "hours")
    d24 = as.difftime(24L, units = "hours")

    w25 = as.numeric(d25, units = inc.units) / as.numeric(increment)
    w24 = as.numeric(d24, units = inc.units) / as.numeric(increment)
    w25.before = sum(seq(w25) < ceiling(w25 / 2))
    w25.after = sum(seq(w25) > ceiling(w25 / 2))
    w24.before = sum(seq(w24) < ceiling(w24 / 2))
    w24.after = sum(seq(w24) > ceiling(w24 / 2))

    offset = as.numeric(as.difftime(1L, units = "hours"),
                        units = inc.units) / as.numeric(increment)

    (slide_dbl(lag(x, offset), roll_fun, .complete = TRUE,
               .before = w24.before, .after = w24.after) +
            slide_dbl(lead(x, offset), roll_fun, .complete = TRUE,
                      .before = w24.before, .after = w24.after) +
            slide_dbl(x, roll_fun, .complete = TRUE,
                      .before = w25.before, .after = w25.after)) / 3.0
}

# Function to determine day/night from Mike Dodrill
day_light <- function(date_time, loc = "old_river"){

    if(loc == "old_river"){
        # junction at head of Old River
        lat = 37.808168
        lon = -121.327446
    }

    if(loc == "turner_cut"){
        # junction at turner cut
        lat = 38.0060934678955
        lon = -121.45293254879358
    }

    date_in = as.Date(date_time)

    # in Rebecca's meta data it says "All times are in Pacific Local Time (PLT)" -- I think this is correct
    sun = suncalc::getSunlightTimes(date = date_in, lat = lat, lon = lon,
                                    keep = c("sunrise", "sunset"), tz = "Etc/GMT+8")

    out = ifelse(date_time > sun$sunrise & date_time < sun$sunset, "day", "night")
    return(out)
}

defineBarrier <- function() {
    # Head of Old River barrier info:
    # Exported from DSS gate input file:
    # ORHRB = ${GATEFILE} /HIST+GATE/ORHRB/WEIR_OP//IR-DECADE/DWR-BDO/
    # ORHRB_FALL = ${GATEFILE} /HIST+GATE/ORHRB_FALL/WEIR_OP//IR-DECADE/DWR-BDO/
    barrierOp <- read.csv(barrierOpFile)
    barrierOp$datetime <- dmy_hm(barrierOp$datetime)

    # Combine spring and fall barriers into a single barrier status
    barrierOp[is.na(barrierOp)] <- 0
    barrierOp$barrier <- barrierOp$ORHRB + barrierOp$ORHRB_FALL
    barrierOp$date <- floor_date(barrierOp$datetime, "day")
    barrierOp <- barrierOp %>% select(date, barrier)

    # Create data frame with all dates
    barrier <- data.frame(date=seq(min(barrierOp$date), max(barrierOp$date), by="days"))
    barrier <- left_join(barrier, barrierOp, by="date") %>% fill(barrier, .direction="down")

    barrier$status <- ifelse(barrier$barrier==1, "closed", "open")

    barrier <- barrier %>% select(date, status) %>% filter(status=="closed")
    barrier$date <- date(barrier$date)

    return(barrier)
}

string_to_difftime = function(s) {
    value = as.numeric(strsplit(s, " ")[[c(1, 1)]])
    increment = strsplit(s, " ")[[c(1, 2)]]
    increment = match.arg(increment,
                          c("secs", "mins", "hours", "days", "weeks"))
    as.difftime(value, units = increment)
}

# Calculate the 15-minute transition probabilities at Head of Old River using fitted msm model
calcProbsHOR <- function(yes2011, barrierState, daytime,
                         scaled_net_flow_D, scaled_tidal_D,
                         scaled_net_flow_T, scaled_tidal_T,
                         OOR) {

    if(OOR) {
        p <- matrix(data=missingVal, nrow=3, ncol=3)
    } else {
        cov_list = list(barrier_2=barrierState, yes_11=yes2011, day=daytime,
                        s_g_cfs_2=scaled_net_flow_D, s_g_cfs_3=scaled_net_flow_T,
                        s_t_cfs_2=scaled_tidal_D, s_t_cfs_3=scaled_tidal_T)
        p = pmatrix.msm(fitHOR, t=1, ci="none", covariates=cov_list)
    }

    return(p)
}

# Calculate the 15-minute transition probabilities in Turner Cut using fitted msm model
calcProbsTC <- function(scaled_net_flow_U, scaled_tidal_U,
                        scaled_net_flow_D, scaled_tidal_D,
                        scaled_net_flow_T, scaled_tidal_T,
                        OOR) {

    if(OOR) {
        p <- matrix(data=missingVal, nrow=3, ncol=3)
    } else {
        cov_list <- list(s_g_l_cfs_1=scaled_net_flow_U, s_g_l_cfs_2=scaled_net_flow_D, s_g_l_cfs_3=scaled_net_flow_T,
                         s_t_l_cfs_1=scaled_tidal_U, s_t_l_cfs_2=scaled_tidal_D, s_t_l_cfs_3=scaled_tidal_T)
        p = pmatrix.msm(fitTC, t=1, ci="none", covariates=cov_list)
    }
    return(p)
}

# Load variables from config file after verifying they exist
loadVar <- function(varName) {
    if(is.null(config[[varName]])) {
        stop(paste(varName, "not found in configuration file."))
    }
    else {return (config[[varName]])}
}

runArgsQA <- function() {
    if(is.null(tideFile)) {
        cat("Tide file is NULL. Is it specified in either the config file or command line arguments?\n")
        return(FALSE)
    }
    
    if(!file.exists(tideFile)) {
        cat("Tide file does not exist. Did you specify the correct path?\n")
        cat("Tide file: ", tideFile, "\n")
        return(FALSE)
    }
    
    if(is.na(dmy(transProbsStartDate, tz="Etc/GMT+8"))) {
        cat("Could not parse transProbStartDate. Is it in a form like 03jan2009?\n")
        cat("transProbsStartDate", transProbsStartDate, "\n")
        return(FALSE)
    }
    
    if(is.na(dmy(transProbsEndDate, tz="Etc/GMT+8"))) {
        cat("Could not parse transProbsEndDate. Is it in a form like 03jan2009?\n")
        cat("transProbsEndDate", transProbsEndDate, "\n")
        return(FALSE)
    }
    
    if(!is.numeric(numCores) | numCores<1) {
        cat("Incorrect number of cores specified.\n")
        cat("numCores: ", numCores, "\n")
        return(FALSE)
    }
    
    return(TRUE)
}
####################################################################################################
# Run
####################################################################################################
cat("---------------------------------------------------------\n")
cat("workingDir: ", workingDir, "\n")
setwd(workingDir)

outputDir <- file.path(workingDir, "output")
dir.create(outputDir, showWarnings=F, recursive=T)

# Load variables from command line or configuration file
if(length(args)==(1 + numOptArgs)) {
    tideFile <- args[2]
    transProbsStartDate <- args[3]
    transProbsEndDate <- args[4]
    numCores <- round(as.numeric(args[5]), 0)
} else {
    tideFile <- read_yaml(configFile)$tideFile
    transProbsStartDate <- loadVar("transProbsStartDate")
    transProbsEndDate <- loadVar("transProbsEndDate")
    # Number of CPU cores to use
    numCores <- loadVar("numCores")
}

sampleTime_min <- loadVar("sampleTime_min")

if(sampleTime_min!=expectedSampleTime_min) {
    cat("---------------------------------------------------------\n")
    cat("WARNING: sampleTime_min IS", sampleTime_min, "MINUTES.\n",
        "IT IS STRONGLY RECOMMENDED THAT YOU USE A TIME STEP OF", expectedSampleTime_min, "MINUTES.\n")
    cat("---------------------------------------------------------\n")
}

passedQA <- runArgsQA()
if(!passedQA) {
    stop("One or more configuration settings failed QA check. Aborting.")
}

# Set up parallel processing
registerDoParallel(cores=numCores)

# Read the locations of the stations
stationLoc <- read.csv(stationLocFile)

cat("Reading channel information.\n")
channel <- h5read(tideFile, "/hydro/input/channel")

# Verify that the tide file we're processing has the same channel lengths
# as were assumed during creation of the configuration files
for(i in 1:nrow(stationLoc)) {
    thisStationLoc <- stationLoc[i, ]
    thisChan <- channel[which(channel$chan_no==thisStationLoc$extChannelNum), ]
    
    if(thisStationLoc$channelLen_ft!=thisChan$length) {
        cat("----------------------------------------------------------------------------------------------------------------------\n")
        cat("WARNING:LENGTH FOR CHANNEL", thisStationLoc$extChannelNum, "DOES NOT MATCH VALUE ASSUMED WHEN CREATING CONFIGURATION FILES.\n")
        cat(paste0("ASSUMED VALUE: ", thisStationLoc$channelLen_ft, "; VALUE IN TIDE FILE: ", thisChan$length, "\n"))
    }
}

# Calculate channelFrac
stationLoc$channelFrac <- pmax(0, pmin(stationLoc$channelDist_ft/stationLoc$channelLen_ft, 1))
stationNames <- unique(stationLoc$stationName)

# Read flows for all channels
cat("Reading flows, start datetime, and end datetime...\n")
channelFlows <- h5read(tideFile, "/hydro/data/channel flow")

# Read the start datetime from the channel flow attributes
channelFlowAttrib <- h5readAttributes(tideFile, "hydro/data/channel flow")
startDatetime <- ymd_hms(channelFlowAttrib$start_time, tz="Etc/GMT+8")
timeStep_min <- h5readAttributes(tideFile, "hydro")$'Time interval'
numTimeSteps <- dim(channelFlows)[3]
flowDatetimes <- seq(startDatetime, length=numTimeSteps, by=paste(timeStep_min, "min"))
endDatetime <- flowDatetimes[length(flowDatetimes)]

# Verify that timeStep_min and sampleTime_min are compatible
cat(paste0("Specified output time step: ", sampleTime_min, " minutes. Channel flows time step in tide file: ", timeStep_min, " minutes.\n"))
if(timeStep_min>sampleTime_min) {
    if(timeStep_min%%sampleTime_min!=0) {
        cat(paste0("WARNING: SPECIFIED OUTPUT TIME STEP (sampleTime_min=", sampleTime_min, 
            ") IS NOT A FACTOR OF THE CHANNEL FLOW TIME STEP (", timeStep_min, ").\n"))   
    }
} else if(sampleTime_min>timeStep_min) {
    if(sampleTime_min%%timeStep_min!=0) {
        cat(paste0("WARNING: SPECIFIED OUTPUT TIME STEP (sampleTime_min=", sampleTime_min, 
                   ") IS NOT A MULTIPLE OF THE CHANNEL FLOW TIME STEP (", timeStep_min, ").\n")) 
    }
}

# All times are in PST (GMT+8)
transProbsStartDatetime <- dmy(transProbsStartDate, tz="Etc/GMT+8")
transProbsEndDatetime <- dmy(transProbsEndDate, tz="Etc/GMT+8")

cat("Tide file: ", tideFile, "\n")
cat("Range of data available in tide file:", format(startDatetime, "%Y-%m-%d %H:%M:%S"), "to", format(endDatetime, "%Y-%m-%d %H:%M:%S"), "\n")
cat("Range of data to extract:", format(transProbsStartDatetime, "%Y-%m-%d %H:%M:%S"), "to", format(transProbsEndDatetime, "%Y-%m-%d %H:%M:%S"), "\n")

# Verify that the tide file range encompasses the requested range, including a buffer for TClag_min
if(transProbsStartDatetime>=transProbsEndDatetime) {
    stop("Start of requested datetime range cannot be the same as or after the end of the requested datetime range. Aborting.")
}
if((transProbsStartDatetime - minutes(TClag_min))<startDatetime | (transProbsEndDatetime + minutes(TClag_min))>endDatetime) {
    stopMessage <- "Requested datetime range of data is outside of the range covered by the tide file. Aborting.\n\n"
    stopMessage <- paste(stopMessage, "\nNote: requested datetime range must be at least", TClag_min, 
                         "minutes after (before) start (end) of datetime range covered by the tide file.\n")
    stop(stopMessage)
}

# Read the (external) channel numbers
channelNums = h5read(tideFile, "/hydro/geometry/channel_number")

# Create data frame with channelNums and channelFracs for each time step and station
datetimes <- seq(startDatetime, endDatetime, sampleTime_min*60)
datetimes <- data.frame(datetime=datetimes)
datetimes$year <- year(datetimes$datetime)

# Expand stationLoc to include entries for all years
stationLocByYear <- data.frame(year=seq(min(datetimes$year), max(datetimes$year)), ID=1)
stationNamesDF <- data.frame(stationName=stationNames, ID=1)
stationLocByYear <- full_join(stationLocByYear, stationNamesDF, by="ID", relationship="many-to-many")
stationLocByYear$ID <- NULL

for(i in 1:nrow(stationLoc)) {
    thisStationLoc <- stationLoc[i, ]
    thisIndices <- stationLocByYear$stationName==thisStationLoc$stationName &
        stationLocByYear$year>=thisStationLoc$startYear & stationLocByYear$year<=thisStationLoc$endYear
    stationLocByYear[thisIndices, "channelNum"] <- thisStationLoc$extChannelNum
    stationLocByYear[thisIndices, "channelFrac"] <- thisStationLoc$channelFrac
}

stationLocByDatetime <- left_join(datetimes, stationLocByYear, by="year", relationship="many-to-many")

stationChannelNums <- unique(stationLocByDatetime$channelNum)

# Extract flows for all channels
cat("Extracting flow data from tide file.\n")
DSM2flowList <- list()
for(i in 1:length(stationChannelNums)) {
    thisChannelNum <- stationChannelNums[i]
    thisChannelIndex <- which(channelNums==thisChannelNum)

    thisFlow <- data.frame(datetime=flowDatetimes,
                           upFlow=channelFlows[1, thisChannelIndex, ],
                           downFlow=channelFlows[2, thisChannelIndex, ])

    # Upsample
    thisFlow <- left_join(datetimes, thisFlow, by="datetime")
    thisFlow$upFlow <- na_interpolation(thisFlow$upFlow)
    thisFlow$downFlow <- na_interpolation(thisFlow$downFlow)

    thisFlow$channelNum <- thisChannelNum

    DSM2flowList[[i]] <- thisFlow
}
DSM2flows <- bind_rows(DSM2flowList)

# Combine flows with station location information and calculate interpolated flow
stationFlow <- left_join(stationLocByDatetime, DSM2flows, by=c("datetime", "year", "channelNum"))
stationFlow <- stationFlow %>% mutate(flow=upFlow + channelFrac*(downFlow-upFlow))

# Apply the Godin filter
cat("Applying Godin filter.\n")
stationFlow <- stationFlow %>% group_by(stationName) %>% mutate(netFlow=smoothGodin(flow, increment=paste(sampleTime_min, "mins")))
stationFlow$tidalFlow <- stationFlow$flow - stationFlow$netFlow

stationFlow <- as.data.frame(stationFlow)

# Apply lag at Turner Cut
for(stationName in TCstationNames) {
    stationFlow[stationFlow$stationName==stationName, "datetime"] <-
        stationFlow[stationFlow$stationName==stationName, "datetime"] + minutes(TClag_min)
}

stationFlow <- stationFlow %>% select(datetime, stationName, netFlow, tidalFlow) %>% filter(!is.na(tidalFlow))

# Load routing model coefficients and scaling data
flowScaling <- read.csv(flowScalingFile)

# Apply flow scaling
stationFlow <- left_join(stationFlow, flowScaling, by="stationName")
stationFlow <- stationFlow %>% mutate(netFlowScaled=(netFlow-netMean)/netStd,
                                      tidalFlowScaled=(tidalFlow-tidalMean)/tidalStd)

# Define barrier status
barrier <- defineBarrier()
stationFlow$barrier <- ifelse(date(stationFlow$datetime) %in% barrier$date &
                                  stationFlow$stationName %in% HORstationNames, "Closed", "Open")

# Identify flow conditions that are outside of the ranges used to fit the model
flowBounds <- read.csv(flowBoundsFile)
flowBounds$stationName <- paste0(flowBounds$location, "_", flowBounds$state)
flowBounds <- flowBounds[, c("stationName", "measure", "barrier", "min", "max")]
flowBounds <- flowBounds %>% pivot_wider(id_cols=c("stationName", "barrier"), names_from=measure, values_from=c("min", "max"))

# Mark flows that are out of bounds in a single channel
stationFlow <- left_join(stationFlow, flowBounds, by=c("stationName", "barrier"))
stationFlow <- stationFlow %>% mutate(OOR=netFlow<min_Net | netFlow>max_Net | tidalFlow<min_Tidal | tidalFlow>max_Tidal)

# Identify datetimes with flows out of bounds in any channel
HORoOR <- stationFlow %>% filter(stationName %in% HORstationNames) %>% select(datetime, stationName, OOR) %>%
    pivot_wider(id_cols=datetime, names_from=stationName, values_from=OOR) %>%
    mutate(OOR=HOR_U | HOR_D | HOR_T) %>% select(datetime, OOR)
TCoOR <- stationFlow %>% filter(stationName %in% TCstationNames) %>% select(datetime, stationName, OOR) %>%
    pivot_wider(id_cols=datetime, names_from=stationName, values_from=OOR) %>%
    mutate(OOR=TC_U | TC_D | TC_T) %>% select(datetime, OOR)

# Drop columns used to calculate OOR from stationFlow
stationFlow <- stationFlow %>% select(datetime:barrier)

# Load fitted models
fitHOR <- readRDS(fitHORfile)
fitTC <- readRDS(fitTCfile)

# Create a logfile to monitor progress
logFile <- file.path(workingDir, "routingPreprocessor.log")
cat("\nCalculating transition probabilities. Track progress in logfile:", logFile, "\n")
cat("Number of cores to use (numCores):", numCores, "\n")
cat("\nNOTE: IF YOU ENCOUNTER AN ERROR SIMILAR TO 'Error in serialize', YOU MAY NEED TO REDUCE numCores IN THE CONFIGURATION FILE.\n")
cat("routingPreprocessor.R logfile\n", file=logFile)
######################################################
# Calculate Head of Old River transition probabilities

# Create flows data frame for calculating transition probabilities
modelHORflow <- stationFlow %>% filter(datetime>transProbsStartDatetime, datetime<transProbsEndDatetime, stationName %in% HORstationNames) %>%
    select(datetime, stationName, netFlowScaled, tidalFlowScaled, barrier) %>%
    pivot_wider(id_cols=datetime, names_from=stationName, values_from=netFlowScaled:barrier)
modelHORflow <- modelHORflow %>% mutate(barrier=barrier_HOR_U) %>% select(datetime, starts_with("netFlow"), starts_with("tidalFlow"), barrier)
modelHORflow <- left_join(modelHORflow, HORoOR, by="datetime")

for (transition in c("qUD", "qUT", "qDU", "qDT", "qTU", "qTD")) {
    modelHORflow[, transition] <- NA
}
modelHORflow <- as.data.frame(modelHORflow)

# Calculate transition probabilities using msm
r <- foreach(i=1:nrow(modelHORflow), .combine=rbind, .packages=c("lubridate", "imputeTS", "slider", "msm")) %dopar% {

    if(i%%1000 == 0) {
        cat("HOR: calculating transition probabilities for row", i, "of", nrow(modelHORflow), "\n",
            file=logFile, append=T)
    }

    thisYear <- year(modelHORflow[i, "datetime"])
    thisYear2011 <- ifelse(thisYear==2011 & use2011, 1, 0)
    thisDaytime <- ifelse(day_light(modelHORflow$datetime[i])=="day", "2_day", "1_night")

    thisProbs <- calcProbsHOR(thisYear2011, modelHORflow[i, "barrier"], thisDaytime,
                              modelHORflow[i, "netFlowScaled_HOR_D"], modelHORflow[i, "tidalFlowScaled_HOR_D"],
                              modelHORflow[i, "netFlowScaled_HOR_T"], modelHORflow[i, "tidalFlowScaled_HOR_T"],
                              modelHORflow[i, "OOR"])

    data.frame(qUD=thisProbs[1, 2], qUT=thisProbs[1, 3], qDU=thisProbs[2, 1],
               qDT=thisProbs[2, 3], qTU=thisProbs[3, 1], qTD=thisProbs[3, 2])
}
cat("Assembling transition probabilities.\n", file=logFile, append=T)
modelHORflow[, c("qUD", "qUT", "qDU", "qDT", "qTU", "qTD")] <- r
######################################################
# Calculate Turner Cut transition probabilities

# Create flows data frame for calculating transition probabilities
modelTCflow <- stationFlow %>% filter(datetime>transProbsStartDatetime, datetime<transProbsEndDatetime, stationName %in% TCstationNames) %>%
    select(datetime, stationName, netFlowScaled, tidalFlowScaled) %>%
    pivot_wider(id_cols=datetime, names_from=stationName, values_from=netFlowScaled:tidalFlowScaled)
modelTCflow <- left_join(modelTCflow, TCoOR, by="datetime")

for (transition in c("qUD", "qUT", "qDU", "qDT", "qTU", "qTD")) {
    modelTCflow[, transition] <- NA
}
modelTCflow <- as.data.frame(modelTCflow)

# Calculate transition probabilities using msm
r <- foreach(i=1:nrow(modelTCflow), .combine=rbind, .packages=c("lubridate", "imputeTS", "slider", "msm")) %dopar% {

    if(i%%1000 == 0) {
        cat("TC: calculating transition probabilities for row", i, "of", nrow(modelTCflow), "\n",
            file=logFile, append=T)
    }

    thisProbs <- calcProbsTC(modelTCflow[i, "netFlowScaled_TC_U"], modelTCflow[i, "tidalFlowScaled_TC_U"],
                             modelTCflow[i, "netFlowScaled_TC_D"], modelTCflow[i, "tidalFlowScaled_TC_D"],
                             modelTCflow[i, "netFlowScaled_TC_T"], modelTCflow[i, "tidalFlowScaled_TC_T"],
                             modelTCflow[i, "OOR"])

    data.frame(qUD=thisProbs[1, 2], qUT=thisProbs[1, 3], qDU=thisProbs[2, 1],
               qDT=thisProbs[2, 3], qTU=thisProbs[3, 1], qTD=thisProbs[3, 2])
}
cat("Assembling transition probabilities.\n", file=logFile, append=T)
modelTCflow[, c("qUD", "qUT", "qDU", "qDT", "qTU", "qTD")] <- r
######################################################
# Combine HOR and TC transition probabilities and write to an output file
transProbsHOR <- modelHORflow %>% select(datetime, qUD, qUT, qDU, qDT, qTU, qTD) %>% mutate(junction="HOR")
transProbsTC <- modelTCflow %>% select(datetime, qUD, qUT, qDU, qDT, qTU, qTD) %>% mutate(junction="TC")
transProbs <- bind_rows(transProbsHOR, transProbsTC)

# Ensure that the HOR and TC transProbs cover the same date ranges
minDatetime <- max(min(transProbsHOR$datetime), min(transProbsTC$datetime))
maxDatetime <- min(max(transProbsHOR$datetime), max(transProbsTC$datetime))
transProbs <- transProbs %>% filter(datetime>=minDatetime, datetime<=maxDatetime)

cat("Saving transition probabilities to", file.path(outputDir, "transProbs.csv"), "\n")
transProbs <- transProbs %>% pivot_longer(cols=qUD:qTD, names_to="transition", values_to="transProb") %>%
    select(junction, datetime, transition, transProb) %>% arrange(datetime, junction, transition)
transProbs$datetime <- format(transProbs$datetime, "%Y-%m-%d %H:%M:%S")

outputFile <- file.path(outputDir, "transProbs.csv")
write.csv(transProbs, file=outputFile, row.names=F, quote=F)

cat("Done. Transition probabilities saved to:", outputFile, "\n")
cat("=========================================================\n")