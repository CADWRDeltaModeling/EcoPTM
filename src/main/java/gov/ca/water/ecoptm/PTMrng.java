package gov.ca.water.ecoptm;

import org.apache.commons.rng.UniformRandomProvider;
import org.apache.commons.rng.sampling.distribution.GaussianSampler;
import org.apache.commons.rng.sampling.distribution.MarsagliaNormalizedGaussianSampler;
import org.apache.commons.rng.sampling.distribution.NormalizedGaussianSampler;
import org.apache.commons.rng.sampling.distribution.SharedStateContinuousSampler;
import org.apache.commons.rng.simple.RandomSource;

/**
 * Random number generator used by Particle, Waterbody, PTMUtil, and Node classes
 * 
 * @author Doug Jackson (QEDA Consulting, LLC)
 */
public class PTMrng {
	
	private UniformRandomProvider RNG = null;
	private SharedStateContinuousSampler gaussianSampler = null;
	
	public PTMrng(int randomSeed) {
		// Create a Mersenne Twister uniform random number generator
		RNG = RandomSource.MT.create(randomSeed);
		
		// Create a Gaussian RNG
		NormalizedGaussianSampler sampler = MarsagliaNormalizedGaussianSampler.of(RNG);
		gaussianSampler = GaussianSampler.of(sampler, 0.0, 1.0);
	}
	
	/**
	 * Generate a random number from a uniform distribution
	 * @return						random number from a uniform distribution
	 */
	public float getRandomNumber() {
		return RNG.nextFloat();
	}
	
	/**
	 * Generate a random number from a Gaussian distribution
	 * @return
	 */
	public double getGaussian() {
		return gaussianSampler.sample();
	}

}
