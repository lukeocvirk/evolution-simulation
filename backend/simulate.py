import random

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
    current_id = 1

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
                    id=current_id,
                )

                molecules.append(new_molecule)

        # Determine if molecule limit has been breached
        no_reproduction = True if len(molecules) >= molecule_limit else False

        # Run death simulation for each molecule
        for molecule in molecules:
            # Decide if the molecule will die
            do_die = random.uniform(0.0, 100.0)
            if do_die < molecule.death_rate:
                molecules.remove(molecule)
                pass

        # Run reproduction simulation for each molecule
        for molecule in molecules:
            # Check if reproduction is available
            if no_reproduction == True:
                break

            do_reproduce = random.uniform(0.0, 100.0)
            if do_reproduce < molecule.reproduction_rate:

                # Decide if the child molecule will mutate
                do_mutate = random.uniform(0.0, 100.0)
                if do_mutate < molecule.mutation_rate:
                    current_id += 1

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
                        id=current_id,
                    )
                    molecules.append(new_molecule)

                    # Log the new molecule
                    with open("output/molecules.txt", "a") as f:
                        f.write(f"ID: {current_id} | R: {reproduce_chance:.2f} - M: {mutate_chance:.2f} - D: {death_chance:.2f}\n")
                    pass

                # Create new molecule copy
                new_molecule = Molecule(
                    reproduction_rate=molecule.reproduction_rate,
                    mutation_rate=molecule.mutation_rate,
                    death_rate=molecule.death_rate,
                    id=molecule.id,
                )
                molecules.append(new_molecule)

        # Record results for this timestep
        with open("output/output.txt", "a") as f:
            f.write(f"T-{timestep} | {len(molecules)} molecules")
            for i in range(current_id):
                if sum(molecule.id == i+1 for molecule in molecules) > 0:
                    f.write(f" | {i+1}: {sum(molecule.id == i+1 for molecule in molecules)}")
            f.write("\n")

        # End simulation if maximum timesteps reached
        if n_timesteps != -1 and timestep >= n_timesteps:
            break

    # Output final state stats
    most = -1
    winning_id = -1
    num_species = 0
    for i in range(current_id):
        n_molecules = sum(molecule.id == i+1 for molecule in molecules)
        if n_molecules > most:
            most = sum(molecule.id == i+1 for molecule in molecules)
            winning_id = i+1
        if n_molecules > 0:
            num_species += 1

    with open("output/final.txt", "a") as f:
        f.write(f"Winner: Species {winning_id} with {most} molecules!\n")
        f.write(f"Total molecules: {len(molecules)}\n")
        f.write(f"Total unique species: {current_id}\n")
        f.write(f"Surviving unique species: {num_species}\n")