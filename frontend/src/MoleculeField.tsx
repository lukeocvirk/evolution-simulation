import { useEffect, useRef, type JSX } from "react";

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
};

export default function MoleculeField(): JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const moleculesRef = useRef<MoleculeDTO[]>([]);
  const rafRef = useRef<number | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

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
    }

    const ws = new WebSocket("ws://localhost:8000/ws");
    wsRef.current = ws;

    ws.onopen = () => {
      // Optional: prime with a no-op step
      // ws.send(JSON.stringify({ type: "step", dt: 0 }));
    };

    ws.onmessage = (ev) => {
      try {
        const state: StateDTO = JSON.parse(ev.data);
        moleculesRef.current = state.molecules;
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

      const radius = 8; // make molecules appear wider
      for (const m of moleculesRef.current) {
        ctx.beginPath();
        ctx.arc(m.x * w, m.y * h, radius, 0, Math.PI * 2);
        ctx.fillStyle = m.colour ?? speciesColour(m.species_id);
        ctx.fill();
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
    };
  }, []);

  return (
    <div style={{ width: "100%", height: "70vh", background: "black", borderRadius: 12 }}>
      <canvas
        ref={canvasRef}
        style={{ width: "100%", height: "100%", display: "block" }}
      />
    </div>
  );
}

function speciesColour(species_id: number): string {
  const hue = (species_id * 137.508) % 360;
  return `hsl(${hue}, 65%, 60%)`;
}
