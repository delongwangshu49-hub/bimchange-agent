import * as THREE from "./vendor/three.module.js";

// A visual XY reference, not an inferred building floor or structural axis grid.
export function createReferenceGrid(bounds) {
  const size = bounds.getSize(new THREE.Vector3());
  const centre = bounds.getCenter(new THREE.Vector3());
  const span = Math.max(size.x, size.y, 12) * 2;
  const minimumStep = Math.max(1, span / 80);
  const magnitude = 10 ** Math.floor(Math.log10(minimumStep));
  const step = [1, 2, 5, 10].map((value) => value * magnitude)
    .find((value) => value >= minimumStep);
  const halfCells = Math.ceil(span / (2 * step));
  const centreX = Math.round(centre.x / step);
  const centreY = Math.round(centre.y / step);
  const lowX = (centreX - halfCells) * step, highX = (centreX + halfCells) * step;
  const lowY = (centreY - halfCells) * step, highY = (centreY + halfCells) * step;
  const elevation = bounds.min.z - Math.max(0.01, step * 0.01);
  const minor = [], major = [];
  for (let offset = -halfCells; offset <= halfCells; offset += 1) {
    const ix = centreX + offset, iy = centreY + offset;
    (ix % 5 === 0 ? major : minor).push(ix * step, lowY, elevation, ix * step, highY, elevation);
    (iy % 5 === 0 ? major : minor).push(lowX, iy * step, elevation, highX, iy * step, elevation);
  }
  const group = new THREE.Group();
  group.name = "visual-reference-grid";
  for (const [vertices, colour] of [[minor, 0x303030], [major, 0x535353]]) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
    const material = new THREE.LineBasicMaterial({ color: colour, toneMapped: false });
    group.add(new THREE.LineSegments(geometry, material));
  }
  group.userData.referenceGrid = {
    spacingM: step, majorSpacingM: step * 5, elevationM: elevation,
    lineSegments: (minor.length + major.length) / 6,
    plane: "XY", background: "#000000", buildingAxes: false,
  };
  return group;
}
