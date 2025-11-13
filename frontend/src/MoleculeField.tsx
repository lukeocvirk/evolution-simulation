import { useEffect, useRef, useState, type JSX } from "react";

type MoleculeDTO = {
  entity_id: number;
  species_id: number;
  x: number;
  y: number;
  colour?: string;
};

type StateDTO = {
  timestep: number;
  molecules: MoleculeDTO[];
  paused?: boolean;
  molecule_limit?: number;
};

export default function MoleculeField(): JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const moleculesRef = useRef<MoleculeDTO[]>([]);
  const rafRef = useRef<number | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [paused, setPaused] = useState(false);
  const [moleculeLimit, setMoleculeLimit] = useState<number>(1000);
  const pausedRef = useRef(false);
  const limitPendingRef = useRef<{ pending: boolean; target: number }>({ pending: false, target: 1000 });
  const limitDebounceRef = useRef<number | null>(null);
  // Track a pending pause/resume toggle to avoid UI flicker from out-of-order snapshots
  const pendingPauseRef = useRef<{ pending: boolean; target: boolean; retries: number }>({ pending: false, target: false, retries: 0 });
  const retryTimerRef = useRef<number | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext("2d")!;

    function resize(): void {
      const dpr = window.devicePixelRatio || 1;
      const { width, height } = canvas.getBoundingClientRect();
      const displayWidth = Math.max(1, Math.floor(width * dpr));
      const displayHeight = Math.max(1, Math.floor(height * dpr));
      if (canvas.width !== displayWidth || canvas.height !== displayHeight) {
        canvas.width = displayWidth;
        canvas.height = displayHeight;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      // Inform backend of viewport and draw radius so it can bounce with margins
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        const radiusPx = 8; // must match draw radius below
        wsRef.current.send(
          JSON.stringify({
            type: "viewport",
            width: Math.max(1, Math.floor(width)),
            height: Math.max(1, Math.floor(height)),
            radius_px: radiusPx,
          })
        );
      }
    }

    const ws = new WebSocket("ws://localhost:8000/ws");
    wsRef.current = ws;

    ws.onopen = () => {
      // Send viewport immediately on connect so backend sets bounce margins
      resize();
    };

    ws.onmessage = (ev) => {
      try {
        const state: StateDTO = JSON.parse(ev.data);
        moleculesRef.current = state.molecules;
        if (typeof state.paused === "boolean") {
          const pending = pendingPauseRef.current;
          if (pending.pending) {
            // Only accept server paused value when it matches our requested target
            if (state.paused === pending.target) {
              setPaused(state.paused);
              pausedRef.current = state.paused;
              pendingPauseRef.current = { pending: false, target: pending.target, retries: 0 };
              if (retryTimerRef.current !== null) {
                window.clearTimeout(retryTimerRef.current);
                retryTimerRef.current = null;
              }
            }
            // Otherwise ignore this snapshot's paused field to prevent flicker
          } else {
            setPaused(state.paused);
            pausedRef.current = state.paused;
          }
        }
        if (typeof state.molecule_limit === "number") {
          const serverLimit = state.molecule_limit;
          const lp = limitPendingRef.current;
          if (lp.pending) {
            if (serverLimit === lp.target) {
              setMoleculeLimit(serverLimit);
              limitPendingRef.current = { pending: false, target: lp.target };
            } // else ignore older snapshot
          } else {
            setMoleculeLimit(serverLimit);
          }
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
    };

    resize();
    let last = performance.now();

    function draw(): void {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);

      const radius = 8; // draw radius in px; backend uses this to set bounce margins
      for (const m of moleculesRef.current) {
        ctx.beginPath();
        ctx.arc(m.x * w, m.y * h, radius, 0, Math.PI * 2);
        ctx.fillStyle = m.colour ?? speciesColour(m.species_id);
        ctx.fill();
      }

      // Draw a simple overlay when paused
      if (pausedRef.current) {
        ctx.save();
        ctx.globalAlpha = 0.35;
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, w, h);
        ctx.restore();

        ctx.save();
        ctx.fillStyle = "#eaeaea";
        ctx.font = "bold 24px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText("Paused", w / 2, h / 2);
        ctx.restore();
      }
    }

    function loop(now: number): void {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;

      draw();
      rafRef.current = requestAnimationFrame(loop);
    }

    rafRef.current = requestAnimationFrame(loop);

    const ro = new ResizeObserver(() => resize());
    ro.observe(canvas);

    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      ro.disconnect();
      ws.close();
      pendingPauseRef.current = { pending: false, target: false, retries: 0 };
      if (retryTimerRef.current !== null) {
        window.clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
    };
  }, []);

  function togglePause(): void {
    const next = !paused;
    setPaused(next); // optimistic update; server echo will confirm
    pausedRef.current = next;
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: next ? "pause" : "resume" }));
    }
    pendingPauseRef.current = { pending: true, target: next, retries: 0 };
    // Start a short retry loop in case the control message is lost
    const scheduleRetry = () => {
      const pending = pendingPauseRef.current;
      if (!pending.pending) return; // already acknowledged
      if (pending.retries >= 5) return; // give up after a few tries
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: pending.target ? "pause" : "resume" }));
        pendingPauseRef.current = { ...pending, retries: pending.retries + 1 };
      }
      retryTimerRef.current = window.setTimeout(scheduleRetry, 250);
    };
    if (retryTimerRef.current !== null) window.clearTimeout(retryTimerRef.current);
    retryTimerRef.current = window.setTimeout(scheduleRetry, 250);
  }

  function resetSim(): void {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "reset" }));
    }
  }

  return (
    <div style={{ width: "100%" }}>
      <div style={{ width: "100%", height: "70vh", background: "black", borderRadius: 12 }}>
        <canvas
          ref={canvasRef}
          style={{ width: "100%", height: "100%", display: "block" }}
        />
      </div>
      <div style={{ marginTop: 8, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button
            onClick={togglePause}
            style={{
              padding: "6px 10px",
              borderRadius: 6,
              border: "1px solid #333",
              background: paused ? "#100958ff" : "#100958ff",
              color: "#d4d7fcff",
              cursor: "pointer",
            }}
          >
            {paused ? "Play" : "Pause"}
          </button>
          <label style={{ color: "#100958ff", fontSize: 14 }}>
            Molecule limit: <strong>{moleculeLimit}</strong>
          </label>
          <input
            type="range"
          min={50}
          max={2500}
          step={50}
            value={moleculeLimit}
            onChange={(e) => {
              const next = Number(e.target.value);
              setMoleculeLimit(next);
              // Ignore older snapshots until ACK for this target arrives
              limitPendingRef.current = { pending: true, target: next };
              // Debounce send
              if (limitDebounceRef.current !== null) window.clearTimeout(limitDebounceRef.current);
              limitDebounceRef.current = window.setTimeout(() => {
                if (wsRef.current?.readyState === WebSocket.OPEN) {
                  wsRef.current.send(JSON.stringify({ type: "set_molecule_limit", value: next }));
                }
              }, 300);
            }}
            style={{ width: 240 }}
          />
        </div>
        <div>
          <button
            onClick={resetSim}
            style={{
              padding: "6px 10px",
              borderRadius: 6,
              border: "1px solid #333",
              background: "#100958ff",
              color: "#eaeaea",
              cursor: "pointer",
            }}
          >
            Reset
          </button>
        </div>
      </div>
    </div>
  );
}

function speciesColour(species_id: number): string {
  const hue = (species_id * 137.508) % 360;
  return `hsl(${hue}, 65%, 60%)`;
}
