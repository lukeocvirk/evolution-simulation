from simulate import run_simulation

def main() -> None:
    """
    Runs the simulation until the user ends the program.
    """
    # Clear output files
    for filename in ["output/output.txt", "output/molecules.txt"]:
        open(filename, "w").close()

    run_simulation(1000, 50.0, 0.5)
    

if __name__ == "__main__":
    main()