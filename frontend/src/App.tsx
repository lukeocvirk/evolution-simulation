import type { JSX } from "react";
import MoleculeField from "./MoleculeField";

export default function App(): JSX.Element {
  return (
    <main style={{ padding: 16, color: "#100958ff", background: "#d4d7fcff", minHeight: "100vh" }}>
      <h1 style={{ marginBottom: 8 }}>Evolution Simulator</h1>
      <p style={{ marginTop: 0, opacity: 0.8 }}>
        Project by Luke Ocvirk.<br />Written in Python with React for UI, canvas for animation.
      </p>
      <MoleculeField />
    </main>
  );
}
