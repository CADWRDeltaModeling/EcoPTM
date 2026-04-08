package gov.ca.water.ecoptm;

/**
 * Object corresponding to a gate in the DSM2 HYDRO grid
 * 
 * @author Doug Jackson (QEDA Consulting, LLC)
 *
 */
public class GridGate {
	public final int type = Grid.OBJ_GATE;
	
	private String name, fromObj, fromID;
	private int toExtNode, toIntNode, gateFlowIndex, devFlowIndex, fromEnvIndex;
	private float leakage, timeAvgLeakage;
	private Waterbody waterbody;
	
	public GridGate(String name, String fromObj, String fromID, int toExtNode, int gateFlowIndex, int devFlowIndex) {
		this.name = name;
		this.fromObj = fromObj;
		this.fromID = fromID;
		this.toExtNode = toExtNode;
		this.gateFlowIndex = gateFlowIndex;
		this.devFlowIndex = devFlowIndex;
		
		toIntNode = PTMFixedData.getIntNodeNum(toExtNode);
		
		waterbody = null;
	}
	
	/**
	 * Set instantaneous and time-averaged leakage values
	 * @param leakage				instantaneous leakage
	 * @param timeAvgLeakage		time-averaged leakage
	 */
	public void setLeakage(float leakage, float timeAvgLeakage) {
		this.leakage = leakage;
		this.timeAvgLeakage = timeAvgLeakage;
		
		if(waterbody==null) {
			lookupWaterbody();
		}
		
		waterbody.setLeakage(leakage, timeAvgLeakage, toIntNode);
	}
	
	/**
	 * Obtain this gate's gate index into the inst_device_flow table
	 * @return						gate index into inst_device_flow table
	 */
	public int getGateFlowIndex() {
		return gateFlowIndex;
	}
	/**
	 * Obtain this gate's device index into the inst_device_flow table
	 * @return						device index into inst_device_flow table
	 */
	public int getDevFlowIndex() {
		return devFlowIndex;
	}
	
	/**
	 * Determine the associated waterbody's internal ID and attach the appropriate Waterbody object
	 */
	private void lookupWaterbody() {
		Waterbody[] allWbs;
		
		// Determine the internal ID
		if(fromObj.equalsIgnoreCase("CHANNEL")) {
			fromEnvIndex = PTMFixedData.getIntChanNum(Integer.parseInt(fromID));
		}
		else if(fromObj.equalsIgnoreCase("RESERVOIR")) {
			fromEnvIndex = PTMFixedData.getIntResNum(fromID);
		}
		
		allWbs = Globals.Environment.getWbArray();
		for(Waterbody wb : allWbs) {
			if(wb!=null && wb.getEnvIndex()==fromEnvIndex) {
				waterbody = wb;
				break;
			}
		}
		
		if(waterbody==null) {
			PTMUtil.systemExit("Could not find waterbody with internal number: " + fromEnvIndex + " Exiting.");
		}
		
	}
}
