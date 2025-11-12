import random

try:
    from .molecule import Molecule  # type: ignore
except ImportError:
    from molecule import Molecule

def run_simulation(n_timesteps: int, molecule_limit: int, spawn_rate: float, variation: float) -> None:
    """
    Runs the simulation until the program is ended.

    :param n_timesteps: The total number of timesteps to simulate; infinite if the value is -1.
    :param molecule_limit: The amount of molecules that the simulation has the 'resources' to support, above which reproduction is disabled.
    :param spawn_rate: The percent chance of a default molecule spawning (as long as there are zero molecules in the simulation).
    :param variation: The maximum variance possible for molecular parameters.
    """
    timestep = 0
    molecules: list[Molecule] = []
    current_species_id = 1
    current_entity_id = 1
    first_colour = randomize_colour()

    while True:
        timestep += 1

        # Spawn molecules if simulation is empty
        if len(molecules) < 1:
            do_spawn = random.uniform(0.0, 100.0)

            # Spawn a molecule
            if do_spawn < spawn_rate:
                new_molecule = Molecule(
                    reproduction_rate=2.0,
                    mutation_rate=4.0,
                    death_rate=1.0,
                    species_id=current_species_id,
                    entity_id=current_entity_id,
                    x=random.uniform(0.0, 1.0),
                    y=random.uniform(0.0, 1.0),
                    colour=first_colour,
                )
                current_entity_id += 1

                molecules.append(new_molecule)

        # Determine if molecule limit has been breached
        no_reproduction = True if len(molecules) >= molecule_limit else False

        # Run death simulation for each molecule
        survivors: list[Molecule] = []
        for molecule in molecules:
            # Decide if the molecule will die
            do_die = random.uniform(0.0, 100.0)
            if do_die >= molecule.death_rate:
                survivors.append(molecule)
        molecules = survivors

        # Run reproduction simulation for each molecule
        children: list[Molecule] = []
        for molecule in molecules:
            # Check if reproduction is available
            if no_reproduction == True:
                break

            do_reproduce = random.uniform(0.0, 100.0)
            if do_reproduce < molecule.reproduction_rate:
                current_entity_id += 1

                # Decide if the child molecule will mutate
                do_mutate = random.uniform(0.0, 100.0)
                if do_mutate < molecule.mutation_rate:
                    current_species_id += 1

                    # Choose new parameters
                    reproduce_chance = molecule.reproduction_rate + random.uniform(0.0, variation) * random.choice([-1, 1])
                    if reproduce_chance < 0.1: reproduce_chance = 0.1
                    mutate_chance = molecule.mutation_rate + random.uniform(0.0, variation) * random.choice([-1, 1])
                    if mutate_chance < 0.1: mutate_chance = 0.1
                    death_chance = molecule.death_rate + random.uniform(0.0, variation) * random.choice([-1, 1])
                    if death_chance < 0.1: death_chance = 0.1

                    # Create new mutated molecule
                    new_molecule = Molecule(
                        reproduction_rate=reproduce_chance,
                        mutation_rate=mutate_chance,
                        death_rate=death_chance,
                        species_id=current_species_id,
                        entity_id=current_entity_id,
                        x=molecule.x,
                        y=molecule.y,
                        colour=randomize_colour(),
                    )
                    children.append(new_molecule)

                    # Log the new molecule
                    log_new_species(current_species_id, reproduce_chance, mutate_chance, death_chance, output_file_path="output/molecules.txt")
                    continue

                # Create new molecule copy
                new_molecule = Molecule(
                    reproduction_rate=molecule.reproduction_rate,
                    mutation_rate=molecule.mutation_rate,
                    death_rate=molecule.death_rate,
                    species_id=molecule.species_id,
                    entity_id=current_entity_id,
                    x=molecule.x,
                    y=molecule.y,
                    colour=molecule.colour,
                )
                children.append(new_molecule)
        molecules.extend(children)

        # Move molecules on the field
        for molecule in molecules:
            molecule.step()

        # Record results for this timestep
        record_results(timestep, molecules, current_species_id, output_file_path="output/output.txt")

        # End simulation if maximum timesteps reached
        if n_timesteps != -1 and timestep >= n_timesteps:
            break

    # Output final state stats
    output_final(molecules, current_species_id, output_file_path="output/final.txt")

def randomize_colour() -> str:
    """
    Chooses a random hex colour for the new molecule species.

    :returns: The chosen hex colour as a string.
    """
    random_integer = random.randint(0, 0xFFFFFF)
    return f"#{random_integer:06x}"

def record_results(timestep: int, molecules: list[Molecule], num_species: int, output_file_path: str) -> None:
    """
    Outputs current simulation information.

    :param timestep: The current timestep.
    :param molecules: The current list of molecules.
    :param num_species: The total number of unique species.
    :param output_file_path: The file to output results to.
    """
    with open(output_file_path, "a") as f:
        f.write(f"T-{timestep} | {len(molecules)} molecules")
        for i in range(num_species):
            if sum(molecule.species_id == i+1 for molecule in molecules) > 0:
                f.write(f" | {i+1}: {sum(molecule.species_id == i+1 for molecule in molecules)}")
        f.write("\n")

def output_final(molecules: list[Molecule], current_species_id: int, output_file_path: str) -> None:
    """
    Outputs the final simulation results.

    :param molecules: The current list of molecules.
    :param current_species_id: The total number of unique species.
    """
    most = -1
    winning_id = -1
    num_species = 0
    for i in range(current_species_id):
        n_molecules = sum(molecule.species_id == i+1 for molecule in molecules)
        if n_molecules > most:
            most = sum(molecule.species_id == i+1 for molecule in molecules)
            winning_id = i+1
        if n_molecules > 0:
            num_species += 1

    with open(output_file_path, "a") as f:
        f.write(f"Winner: Species {winning_id} with {most} molecules!\n")
        f.write(f"Total molecules: {len(molecules)}\n")
        f.write(f"Total unique species: {current_species_id}\n")
        f.write(f"Surviving unique species: {num_species}\n")

def log_new_species(current_species_id: int, reproduce_chance: float, mutate_chance: float, death_chance: float, output_file_path: str) -> None:
    """
    Outputs the
    """
    with open(output_file_path, "a") as f:
        f.write(f"Species ID: {current_species_id} | R: {reproduce_chance:.2f} - M: {mutate_chance:.2f} - D: {death_chance:.2f}\n")