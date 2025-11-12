from __future__ import annotations

import asyncio
import contextlib
import random
import time
from typing import List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import your Molecule; assumes Molecule.step() handles movement + bounce
from backend.molecule import Molecule
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
        self.next_entity_id = 1
        self.molecules: list[Molecule] = []

        # Optional: keep a stable colour per species (first species gets one at first spawn)
        self.species_colour: dict[int, str] = {}

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
        self.next_entity_id = 1
        self.molecules = []
        self.species_colour = {}

    def step(self, dt: float) -> None:
        # Advance one simulation tick. dt is accepted for future use; Molecule.step() handles movement.
        self.timestep += 1

        # Spawn if empty
        if len(self.molecules) < 1:
            if random.uniform(0.0, 100.0) < self.spawn_rate:
                # Ensure species 1 has a colour
                if 1 not in self.species_colour:
                    self.species_colour[1] = randomize_colour()
                m = Molecule(
                    reproduction_rate=2.0,
                    mutation_rate=4.0,
                    death_rate=1.0,
                    species_id=self.current_species_id,  # 1
                    entity_id=self.next_entity_id,
                    x=random.uniform(0.0, 1.0),
                    y=random.uniform(0.0, 1.0),
                    colour=self.species_colour[1],
                )
                self.next_entity_id += 1
                self.molecules.append(m)

        # Determine if molecule limit has been breached (disable reproduction)
        no_reproduction = len(self.molecules) >= self.molecule_limit

        # Death (build survivors; do not remove while iterating)
        survivors: list[Molecule] = []
        for m in self.molecules:
            if random.uniform(0.0, 100.0) >= m.death_rate:
                survivors.append(m)
        self.molecules = survivors

        # Reproduction (either mutated OR copied child)
        if not no_reproduction:
            children: list[Molecule] = []
            for parent in self.molecules:
                if random.uniform(0.0, 100.0) < parent.reproduction_rate:
                    # Decide if the child will mutate
                    if random.uniform(0.0, 100.0) < parent.mutation_rate:
                        # New species
                        self.current_species_id += 1
                        sid = self.current_species_id

                        # Choose new parameters with bounded variation
                        def vary(base: float) -> float:
                            val = base + random.uniform(0.0, self.variation) * random.choice([-1, 1])
                            return val if val >= 0.1 else 0.1

                        reproduce_chance = vary(parent.reproduction_rate)
                        mutate_chance = vary(parent.mutation_rate)
                        death_chance = vary(parent.death_rate)

                        # Assign a colour for this new species
                        col = randomize_colour()
                        self.species_colour[sid] = col

                        child = Molecule(
                            reproduction_rate=reproduce_chance,
                            mutation_rate=mutate_chance,
                            death_rate=death_chance,
                            species_id=sid,
                            entity_id=self.next_entity_id,
                            x=parent.x,
                            y=parent.y,
                            colour=col,
                        )
                        self.next_entity_id += 1
                        children.append(child)
                        # Log the new species creation to file
                        try:
                            log_new_species(
                                sid,
                                reproduce_chance,
                                mutate_chance,
                                death_chance,
                                output_file_path="backend/output/molecules.txt",
                            )
                        except Exception:
                            pass
                    else:
                        # Copy child (same species/params/colour)
                        child = Molecule(
                            reproduction_rate=parent.reproduction_rate,
                            mutation_rate=parent.mutation_rate,
                            death_rate=parent.death_rate,
                            species_id=parent.species_id,
                            entity_id=self.next_entity_id,
                            x=parent.x,
                            y=parent.y,
                            colour=parent.colour,
                        )
                        self.next_entity_id += 1
                        children.append(child)

            if children:
                self.molecules.extend(children)

        # Movement and bounce
        for m in self.molecules:
            # If Molecule.step ever accepts dt, pass it here: m.step(dt)
            m.step()

        # Record results for this timestep to file
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

        # Advance simulation (use fixed tick for stability if preferred)
        try:
            sim.step(dt)
        except Exception:
            # Do not crash the loop on a single-step failure
            pass

        # Prepare payload compatible with Pydantic v2 or v1
        try:
            payload = sim.to_state().model_dump()
        except AttributeError:
            payload = sim.to_state().dict()

        await manager.broadcast(payload)

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
        # Keep the connection alive and optionally process control messages
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_json(), timeout=30.0)
            except asyncio.TimeoutError:
                # No inbound messages; continue to keep the socket alive
                continue

            typ = msg.get("type")
            if typ == "reset":
                sim.reset(
                    molecule_limit=int(msg.get("molecule_limit", sim.molecule_limit)),
                    spawn_rate=float(msg.get("spawn_rate", sim.spawn_rate)),
                    variation=float(msg.get("variation", sim.variation)),
                    seed=msg.get("seed"),
                )
            # Ignore other message types; background loop handles broadcasting

    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception:
        await manager.disconnect(ws)
