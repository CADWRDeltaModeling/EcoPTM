package gov.ca.water.ecoptm;

import java.util.random.RandomGenerator;
import java.util.random.RandomGeneratorFactory;

/**
 * Random number generator used by Particle, Waterbody, PTMUtil, and Node classes
 * 
 * @author Doug Jackson (QEDA Consulting, LLC)
 */
public class PTMrng {
	
	private RandomGenerator RNG = null;
	
	/**
	 * Create a Xoshiro256PlusPlus pseudorandom number generator
	 * @param randomSeed			pseudorandom number generator seed
	 */
	public PTMrng(int randomSeed) {
		RNG = RandomGeneratorFactory.of("Xoshiro256PlusPlus").create(randomSeed);
	}
	
	/**
	 * Generate a random number from a uniform distribution
	 * @return						random number from a uniform distribution
	 */
	public float getUniform() {
		return RNG.nextFloat();
	}
	
	/**
	 * Generate a random number from a Gaussian distribution
	 * @return
	 */
	public double getGaussian() {
		return RNG.nextGaussian();
	}

}
