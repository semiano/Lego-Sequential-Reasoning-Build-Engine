"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

type Placement = { x: number; y: number; z: number; partId: string };

function parsePlacements(content: string): Placement[] {
  const out: Placement[] = [];
  for (const line of content.split("\n")) {
    const tokens = line.trim().split(/\s+/);
    if (tokens.length < 15 || tokens[0] !== "1") {
      continue;
    }
    const x = Number(tokens[2]);
    const y = Number(tokens[3]);
    const z = Number(tokens[4]);
    if (Number.isNaN(x) || Number.isNaN(y) || Number.isNaN(z)) {
      continue;
    }
    out.push({ x, y, z, partId: tokens[tokens.length - 1] });
  }
  return out;
}

export function ThreeViewer({ ldrawContent }: { ldrawContent: string }) {
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!rootRef.current) {
      return;
    }

    const placements = parsePlacements(ldrawContent);
    const width = rootRef.current.clientWidth || 500;
    const height = 320;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x111722);

    const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 10000);
    camera.position.set(180, 140, 180);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    rootRef.current.innerHTML = "";
    rootRef.current.appendChild(renderer.domElement);

    const lightA = new THREE.DirectionalLight(0xffffff, 0.9);
    lightA.position.set(100, 100, 100);
    const lightB = new THREE.AmbientLight(0xffffff, 0.55);
    scene.add(lightA, lightB);

    const grid = new THREE.GridHelper(300, 20, 0x2f4f7f, 0x1d2a3f);
    scene.add(grid);

    const boxGeometry = new THREE.BoxGeometry(20, 12, 20);
    for (const placement of placements) {
      const color = placement.partId.includes("3023") ? 0x8db4ff : 0x7bd88f;
      const mesh = new THREE.Mesh(
        boxGeometry,
        new THREE.MeshStandardMaterial({ color, roughness: 0.65, metalness: 0.1 })
      );
      mesh.position.set(placement.x / 2, placement.y / 2, placement.z / 2);
      scene.add(mesh);
    }

    let raf = 0;
    const animate = () => {
      raf = requestAnimationFrame(animate);
      scene.rotation.y += 0.0025;
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(raf);
      renderer.dispose();
      boxGeometry.dispose();
    };
  }, [ldrawContent]);

  return <div ref={rootRef} style={{ border: "1px solid #2e3540", borderRadius: 8, overflow: "hidden" }} />;
}
