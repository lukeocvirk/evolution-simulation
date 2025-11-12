from pathlib import Path

from simulate import run_simulation

def main() -> None:
    """
    Runs the simulation until the user ends the program.
    """
    # Clear output files
    out_dir = Path(__file__).parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ["output.txt", "molecules.txt", "final.txt"]:
        (out_dir / name).write_text("")

    # Run simulation
    run_simulation(n_timesteps=10000, molecule_limit=1000, spawn_rate=50.0, variation=0.5)
    

if __name__ == "__main__":
    main()