import random

class Molecule:
    """
    The primary molecule type for the simulation, with given starting values.
    """
    reproduction_rate: float
    mutation_rate: float
    death_rate: float
    species_id: int
    entity_id: int
    x: float
    y: float
    vx: float
    vy: float
    colour: str

    def __init__(
        self,
        reproduction_rate,
        mutation_rate,
        death_rate,
        species_id,
        entity_id,
        x,
        y,
        colour,
    ) -> None:
        """
        Initializes the molecule.
        
        :param reproduction_rate: Percent chance of a molecule reproducing each timestep.
        :param mutation_rate: Percent chance of a molecule mutating each timestep.
        :param death_rate: Percent chance of a molecule dying each timestep.
        :param species_id: Unique ID for the molecule's species.
        :param entity_id: Unique ID for the molecule.
        :param x: 'x' position on the field.
        :param y: 'y' position on the field.
        :param colour: Hex representation of the molecule's display colour.
        """
        self.reproduction_rate = reproduction_rate
        self.mutation_rate = mutation_rate
        self.death_rate = death_rate
        self.species_id = species_id
        self.entity_id = entity_id
        self.x = float(x)
        self.y = float(y)
        self.colour = colour

        # Randomize molecule movement speed/direction (slower)
        self.vx = random.choice([-0.0005, 0.0005])
        self.vy = random.choice([-0.0005, 0.0005])

    def step(self, min_x: float = 0.0, max_x: float = 1.0, min_y: float = 0.0, max_y: float = 1.0) -> None:
        """
        Moves the molecule based on its position, velocity.
        """
        self.x += self.vx
        self.y += self.vy

        if self.x < min_x:
            self.x = min_x
            self.vx *= -1
        elif self.x > max_x:
            self.x = max_x
            self.vx *= -1

        if self.y < min_y:
            self.y = min_y
            self.vy *= -1
        elif self.y > max_y:
            self.y = max_y
            self.vy *= -1
