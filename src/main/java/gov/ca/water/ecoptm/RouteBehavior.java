/**
 *
 */
package gov.ca.water.ecoptm;

/**
 * @author xwang
 *
 */
public interface RouteBehavior {
	static final String behaviorType = "ROUTE";
	public void makeRouteDecision(Particle p);
	public void updateCurrentInfo(Waterbody[] allWbs, int CurrentTime);

}
