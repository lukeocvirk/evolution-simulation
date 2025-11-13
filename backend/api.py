from __future__ import annotations

import asyncio
import contextlib
import random
import time
from typing import List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.molecule import Molecule
import logging

# Lightweight logger for control events (doesn't override uvicorn logging)
logger = logging.getLogger("evolution.control")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[evolution] %(asctime)s %(levelname)s: %(message)s"))
    logger.addHandler(_h)
logger.setLevel(logging.INFO)
from backend.simulate import record_results, log_new_species, output_final


# ----- DTOs sent to the frontend -----
class MoleculeDTO(BaseModel):
    entity_id: int
    species_id: int
    x: float
    y: float
    colour: str


class StateDTO(BaseModel):
    timestep: int
    molecules: List[MoleculeDTO]
    paused: bool = False
    molecule_limit: int


# ----- Helpers -----
def randomize_colour() -> str:
    rnd = random.randint(0, 0xFFFFFF)
    return f"#{rnd:06x}"


# ----- Connection management for WebSocket broadcasting -----
class ConnectionManager:
    def __init__(self) -> None:
        self.active: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        self.active.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        self.active.discard(ws)

    async def broadcast(self, payload: dict) -> None:
        stale: list[WebSocket] = []
        for ws in list(self.active):
            try:
                await ws.send_json(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.active.discard(ws)


# ----- Core simulation holder -----
class Simulation:
    def __init__(self, molecule_limit: int, spawn_rate: float, variation: float) -> None:
        self.molecule_limit = molecule_limit
        self.spawn_rate = spawn_rate
        self.variation = variation
        self.timestep = 0
        self.current_species_id = 1
        self.current_entity_id = 1
        self.molecules: list[Molecule] = []
        self.paused: bool = False

        self.margin_x: float = 0.0
        self.margin_y: float = 0.0

        self.species_colour: dict[int, str] = {}
        self.first_colour = randomize_colour()

    def reset(
        self,
        molecule_limit: int,
        spawn_rate: float,
        variation: float,
        seed: Optional[int] = None,
    ) -> None:
        if seed is not None:
            random.seed(seed)

        self.molecule_limit = molecule_limit
        self.spawn_rate = spawn_rate
        self.variation = variation

        self.timestep = 0
        self.current_species_id = 1
        self.current_entity_id = 1
        self.molecules = []
        self.species_colour = {}
        self.first_colour = randomize_colour()

    def step(self, dt: float) -> None:
        # Advance one simulation tick. dt is accepted for future use; Molecule.step() handles movement.
        self.timestep += 1

        # Spawn molecules if simulation is empty
        if len(self.molecules) < 1:
            do_spawn = random.uniform(0.0, 100.0)

            # Spawn a molecule
            if do_spawn < self.spawn_rate:
                new_molecule = Molecule(
                    reproduction_rate=2.0,
                    mutation_rate=4.0,
                    death_rate=1.0,
                    species_id=self.current_species_id,
                    entity_id=self.current_entity_id,
                    x=random.uniform(0.0, 1.0),
                    y=random.uniform(0.0, 1.0),
                    colour=self.first_colour,
                )
                self.current_entity_id += 1

                self.molecules.append(new_molecule)

        # Determine if molecule limit has been breached
        no_reproduction = True if len(self.molecules) >= self.molecule_limit else False

        # Run death simulation for each molecule
        survivors: list[Molecule] = []
        for molecule in self.molecules:
            # Decide if the molecule will die
            do_die = random.uniform(0.0, 100.0)
            if do_die >= molecule.death_rate:
                survivors.append(molecule)
        self.molecules = survivors

        # Run reproduction simulation for each molecule
        children: list[Molecule] = []
        for molecule in self.molecules:
            # Check if reproduction is available
            if no_reproduction == True:
                break

            do_reproduce = random.uniform(0.0, 100.0)
            if do_reproduce < molecule.reproduction_rate:
                self.current_entity_id += 1

                # Decide if the child molecule will mutate
                do_mutate = random.uniform(0.0, 100.0)
                if do_mutate < molecule.mutation_rate:
                    self.current_species_id += 1

                    # Choose new parameters
                    reproduce_chance = molecule.reproduction_rate + random.uniform(0.0, self.variation) * random.choice([-1, 1])
                    if reproduce_chance < 0.1: reproduce_chance = 0.1
                    mutate_chance = molecule.mutation_rate + random.uniform(0.0, self.variation) * random.choice([-1, 1])
                    if mutate_chance < 0.1: mutate_chance = 0.1
                    death_chance = molecule.death_rate + random.uniform(0.0, self.variation) * random.choice([-1, 1])
                    if death_chance < 0.1: death_chance = 0.1

                    # Create new mutated molecule
                    new_molecule = Molecule(
                        reproduction_rate=reproduce_chance,
                        mutation_rate=mutate_chance,
                        death_rate=death_chance,
                        species_id=self.current_species_id,
                        entity_id=self.current_entity_id,
                        x=molecule.x,
                        y=molecule.y,
                        colour=randomize_colour(),
                    )
                    children.append(new_molecule)

                    # Log the new molecule
                    try:
                        log_new_species(
                            self.current_species_id,
                            reproduce_chance,
                            mutate_chance,
                            death_chance,
                            new_molecule.colour,
                            output_file_path="backend/output/molecules.txt",
                        )
                    except Exception:
                        pass
                    continue

                # Create new molecule copy
                new_molecule = Molecule(
                    reproduction_rate=molecule.reproduction_rate,
                    mutation_rate=molecule.mutation_rate,
                    death_rate=molecule.death_rate,
                    species_id=molecule.species_id,
                    entity_id=self.current_entity_id,
                    x=molecule.x,
                    y=molecule.y,
                    colour=molecule.colour,
                )
                children.append(new_molecule)
        self.molecules.extend(children)

        # Move molecules on the field
        for molecule in self.molecules:
            molecule.step(
                min_x=self.margin_x,
                max_x=1.0 - self.margin_x,
                min_y=self.margin_y,
                max_y=1.0 - self.margin_y,
            )

        # Record results for this timestep
        try:
            record_results(
                self.timestep,
                self.molecules,
                self.current_species_id,
                output_file_path="backend/output/output.txt",
            )
        except Exception:
            pass

    def to_state(self) -> StateDTO:
        return StateDTO(
            timestep=self.timestep,
            molecules=[
                MoleculeDTO(
                    entity_id=m.entity_id,
                    species_id=m.species_id,
                    x=m.x,
                    y=m.y,
                    colour=m.colour,
                )
                for m in self.molecules
            ],
            paused=self.paused,
            molecule_limit=self.molecule_limit,
        )


# ----- FastAPI app + CORS -----
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sim = Simulation(molecule_limit=1000, spawn_rate=50.0, variation=0.5)
manager = ConnectionManager()
sim_lock = asyncio.Lock()


# ----- Background ticking loop -----
TICK_HZ = 30.0
TICK_DT = 1.0 / TICK_HZ


async def _tick_loop() -> None:
    last = time.monotonic()
    while True:
        now = time.monotonic()
        dt = now - last
        last = now

        # Only advance the simulation when at least one client is connected
        if not manager.active:
            await asyncio.sleep(TICK_DT)
            continue

        # Advance simulation (guarded by a lock to avoid interleaving
        # with control messages; also broadcast while holding the lock
        # so no stale payload can be sent after a pause/resume toggle)
        async with sim_lock:
            try:
                if not sim.paused:
                    try:
                        sim.step(dt)
                    except Exception:
                        pass
                # Always broadcast current state (even when paused)
                try:
                    payload = sim.to_state().model_dump()
                except AttributeError:
                    payload = sim.to_state().dict()
                await manager.broadcast(payload)
            except Exception:
                pass

        await asyncio.sleep(TICK_DT)


@app.on_event("startup")
async def _on_startup() -> None:
    # Clear output files at start
    for filename in [
        "backend/output/output.txt",
        "backend/output/molecules.txt",
        "backend/output/final.txt",
    ]:
        try:
            open(filename, "w").close()
        except Exception:
            pass
    app.state.loop_task = asyncio.create_task(_tick_loop())


@app.on_event("shutdown")
async def _on_shutdown() -> None:
    task = getattr(app.state, "loop_task", None)
    if task:
        task.cancel()
        with contextlib.suppress(Exception):
            await task
    # Output final summary
    try:
        output_final(
            sim.molecules,
            sim.current_species_id,
            output_file_path="backend/output/final.txt",
        )
    except Exception:
        pass


# ----- REST (optional / debugging) -----
@app.get("/state", response_model=StateDTO)
def get_state() -> StateDTO:
    return sim.to_state()


@app.post("/step", response_model=StateDTO)
def post_step(dt: float = Query(0.033)) -> StateDTO:
    sim.step(dt)
    return sim.to_state()


class ResetParams(BaseModel):
    molecule_limit: int = 1000
    spawn_rate: float = 50.0
    variation: float = 0.5
    seed: Optional[int] = None


@app.post("/reset", response_model=StateDTO)
def post_reset(params: ResetParams) -> StateDTO:
    sim.reset(
        molecule_limit=params.molecule_limit,
        spawn_rate=params.spawn_rate,
        variation=params.variation,
        seed=params.seed,
    )
    return sim.to_state()


# ----- WebSocket (client-driven stepping) -----
@app.websocket("/ws")
async def ws(ws: WebSocket) -> None:
    await ws.accept()
    # If this is the first connection, reset the simulation and clear logs
    first_client = len(manager.active) == 0
    await manager.connect(ws)
    if first_client:
        # Clear output files and reset state so each page load starts fresh
        for filename in [
            "backend/output/output.txt",
            "backend/output/molecules.txt",
            "backend/output/final.txt",
        ]:
            try:
                open(filename, "w").close()
            except Exception:
                pass
        sim.reset(
            molecule_limit=sim.molecule_limit,
            spawn_rate=sim.spawn_rate,
            variation=sim.variation,
            seed=None,
        )
        try:
            logger.info("first client connected; sim reset; paused=%s", sim.paused)
        except Exception:
            pass
    try:
        # Keep the connection alive and optionally process control messages
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_json(), timeout=30.0)
            except asyncio.TimeoutError:
                # No inbound messages; continue to keep the socket alive
                continue

            typ = msg.get("type")
            if typ == "reset":
                async with sim_lock:
                    sim.reset(
                        molecule_limit=int(msg.get("molecule_limit", sim.molecule_limit)),
                        spawn_rate=float(msg.get("spawn_rate", sim.spawn_rate)),
                        variation=float(msg.get("variation", sim.variation)),
                        seed=msg.get("seed"),
                    )
                    try:
                        logger.info("WS reset requested; paused now %s", sim.paused)
                    except Exception:
                        pass
                    try:
                        payload = sim.to_state().model_dump()
                    except AttributeError:
                        payload = sim.to_state().dict()
                    # Direct ACK to this client to avoid interleaving with tick broadcasts
                    await ws.send_json(payload)
            elif typ in {"pause", "resume", "set_paused"}:
                async with sim_lock:
                    if typ == "pause":
                        sim.paused = True
                    elif typ == "resume":
                        sim.paused = False
                    else:
                        val = msg.get("value")
                        # Accept booleans and common truthy/falsey encodings
                        if isinstance(val, bool):
                            sim.paused = val
                        elif isinstance(val, str):
                            sim.paused = val.strip().lower() in {"1", "true", "yes", "on"}
                        elif isinstance(val, (int, float)):
                            sim.paused = bool(val)
                    try:
                        logger.info("WS pause toggle -> paused=%s", sim.paused)
                    except Exception:
                        pass
                    try:
                        payload = sim.to_state().model_dump()
                    except AttributeError:
                        payload = sim.to_state().dict()
                    # Direct ACK to this client to prevent UI flicker; next tick will update others
                    await ws.send_json(payload)
            elif typ == "set_molecule_limit":
                async with sim_lock:
                    val = msg.get("value")
                    try:
                        new_limit = int(val)
                    except Exception:
                        new_limit = sim.molecule_limit
                    if new_limit < 1:
                        new_limit = 1
                    sim.molecule_limit = new_limit
                    try:
                        payload = sim.to_state().model_dump()
                    except AttributeError:
                        payload = sim.to_state().dict()
                    await ws.send_json(payload)
            elif typ == "viewport":
                # Update normalized margins based on current canvas size and draw radius (in px)
                async with sim_lock:
                    try:
                        width = float(msg.get("width", 0))
                        height = float(msg.get("height", 0))
                        radius = float(msg.get("radius_px", 0))
                    except Exception:
                        width = height = radius = 0.0
                    if width > 0 and height > 0 and radius >= 0:
                        sim.margin_x = max(0.0, min(0.5, radius / width))
                        sim.margin_y = max(0.0, min(0.5, radius / height))
                    try:
                        payload = sim.to_state().model_dump()
                    except AttributeError:
                        payload = sim.to_state().dict()
                    await ws.send_json(payload)
            # Ignore other message types; background loop handles broadcasting

    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception:
        await manager.disconnect(ws)
