import random

import numpy as np
from faker import Faker

from Bizpoint.data_generation.config import RANDOM_SEED


def create_generators(seed: int = RANDOM_SEED):
 

    # Python random generator.
    random_generator = random.Random(seed)

    # NumPy random generator.
    numpy_generator = np.random.default_rng(seed)

    # Faker generator.
    fake = Faker()
    fake.seed_instance(seed)

    return random_generator, numpy_generator, fake