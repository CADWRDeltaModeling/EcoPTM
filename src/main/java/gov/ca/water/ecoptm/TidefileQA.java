package gov.ca.water.ecoptm;

/**
 *  Perform various quality assurance (QA) checks on the tidefile.
 * 
 * @author Doug Jackson (QEDA Consulting, LLC)
 */
public class TidefileQA {
	
	private static int numBoundaryWaterbodies, MAX_BOUNDARY_WATERBODIES,
		numChannels, MAX_CHANNELS, channelFlowDim0, channelFlowDim1, channelFlowDim2;
	
	/**
	 * Set variables associated with qext
	 * @param nBW					number of boundary waterbodies
	 * @param MBW					maximum number of boundary waterbodies
	 */
	public static void setQextVals(int nBW, int MBW) {
		numBoundaryWaterbodies = nBW;
		MAX_BOUNDARY_WATERBODIES = MBW;
	}
	
	/**
	 * Set variables associated with channel
	 * @param nC					number of channels
	 * @param mC					maximum number of channels
	 */
	public static void setChannelVals(int nC, int mC) {
		numChannels = nC;
		MAX_CHANNELS = mC;
	}
	
	/**
	 * Run all QA checks associated with data read by PTMFixedData.java
	 */
	public static void runQAfixedData() {
		System.out.println("==================================================================================");
		System.out.println("Performing tidefile fixed data QA checks.");
		
		if(numBoundaryWaterbodies>MAX_BOUNDARY_WATERBODIES) {
			PTMUtil.systemExit("Number of boundary waterbodies in qext table (" + numBoundaryWaterbodies + 
					") exceeds MAX_BOUNDARY_WATERBODIES (" + MAX_BOUNDARY_WATERBODIES + "). Exiting.");
		}
		
		if(numChannels>MAX_CHANNELS) {
			PTMUtil.systemExit("Number of channels in channel table (" + numChannels + 
					") exceeds MAX_CHANNELS (" + MAX_CHANNELS + "). Exiting.");
		}
		
		System.out.println("Passed tidefile fixed data QA checks.");
		System.out.println("==================================================================================");
	}
	
	/**
	 * Set variables associated with channel_flow dimensions
	 * @param cFD0					first dimension of channel_flow
	 * @param cFD1					second dimension of channel_flow
	 * @param cFD2					third dimension of channel_flow
	 */
	public static void setChannelFlowVals(int cFD0, int cFD1, int cFD2) {
		channelFlowDim0 = cFD0;
		channelFlowDim1 = cFD1;
		channelFlowDim2 = cFD2;
	}
	
	public static void runQAhydroInput() {
		System.out.println("==================================================================================");
		System.out.println("Performing tidefile hydro input QA checks.");
		
		if(channelFlowDim0<1) {
			PTMUtil.systemExit("Size of first dimension of channel_flow is " + channelFlowDim0 + 
					" but should be greater than 0. Exiting");
		}
		
		if(channelFlowDim2!=2) {
			PTMUtil.systemExit("Size of third dimension of channel_flow is " + channelFlowDim2 + 
					" but should be 2. Exiting");
		}
		
		System.out.println("Passed tidefile hydro input QA checks.");
		System.out.println("==================================================================================");
	}

}
