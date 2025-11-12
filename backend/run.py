from simulate import run_simulation

def main() -> None:
    """
    Runs the simulation until the user ends the program.
    """
    # Clear output files
    for filename in ["output/output.txt", "output/molecules.txt", "output/final.txt"]:
        open(filename, "w").close()

    run_simulation(n_timesteps=10000, molecule_limit=1000, spawn_rate=50.0, variation=0.5)
    

if __name__ == "__main__":
    main()