/**
 *
 */
package gov.ca.water.ecoptm;

/**
 * @author xwang
 *
 */
public interface SurvivalBehavior {
	static final String behaviorType = "SURVIVAL";
	public void isSurvived(Particle p);

}
