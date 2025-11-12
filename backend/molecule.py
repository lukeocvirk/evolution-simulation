
class Molecule:
    """
    The primary molecule type for the simulation, with given starting values.
    """
    reproduction_rate: float
    mutation_rate: float
    death_rate: float
    id: int

    def __init__(
        self,
        reproduction_rate,
        mutation_rate,
        death_rate,
        id,
    ) -> None:
        """
        :param reproduction_rate: Percent chance of a molecule reproducing each timestep.
        :param mutation_rate: Percent chance of a molecule mutating each timestep.
        :param death_rate: Percent chance of a molecule dying each timestep.
        """
        self.reproduction_rate = reproduction_rate
        self.mutation_rate = mutation_rate
        self.death_rate = death_rate
        self.id = id
