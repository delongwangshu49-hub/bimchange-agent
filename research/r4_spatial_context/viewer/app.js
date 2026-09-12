import * as THREE from "./vendor/three.module.js";
import { GLTFLoader } from "./vendor/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "./vendor/addons/controls/OrbitControls.js";

const canvas = document.querySelector("#viewer");
const status = document.querySelector("#status");
const list = document.querySelector("#change-list");
const details = document.querySelector("#details");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(42, 1, 0.01, 1000);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
scene.add(new THREE.HemisphereLight(0xffffff, 0x263442, 2.2));
const sun = new THREE.DirectionalLight(0xffffff, 2.6);
sun.position.set(8, -10, 14);
scene.add(sun);

let loadedRoot = null;
let manifest = null;
let currentChangeId = null;

function resize() {
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (canvas.width !== Math.floor(width * renderer.getPixelRatio()) || canvas.height !== Math.floor(height * renderer.getPixelRatio())) {
    renderer.setSize(width, height, false);
    camera.aspect = width / Math.max(height, 1);
    camera.updateProjectionMatrix();
  }
}

function animate() {
  resize();
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}
animate();

function label(changeType) {
  return ({ deleted: "Deleted", added: "Added", property_modified: "Property modified" })[changeType] || changeType;
}

function setDetails(item) {
  const rows = [
    ["Change", item.change_id],
    ["GlobalId", item.target_global_id],
    ["IFC role", item.selected_ifc_role],
    ["Scene nodes", String(item.nodes.length)],
    ["GLB SHA-256", item.sha256],
  ];
  details.replaceChildren(...rows.flatMap(([term, value]) => {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = term;
    dd.textContent = value;
    return [dt, dd];
  }));
}

async function showChange(changeId) {
  const item = manifest.scenes.find((candidate) => candidate.change_id === changeId);
  if (!item) throw new Error(`Unknown change_id: ${changeId}`);
  currentChangeId = changeId;
  status.textContent = `Loading ${item.selected_ifc_role} scene…`;
  document.querySelectorAll("button[data-change-id]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.changeId === changeId));
  });
  if (loadedRoot) {
    scene.remove(loadedRoot);
    loadedRoot.traverse((object) => {
      if (object.geometry) object.geometry.dispose();
      if (object.material) object.material.dispose();
    });
  }
  const gltf = await new GLTFLoader().loadAsync(`../${item.file}`);
  loadedRoot = gltf.scene;
  let targetCount = 0;
  loadedRoot.traverse((object) => {
    if (!object.isMesh) return;
    const isTarget = object.userData.global_id === item.target_global_id;
    if (isTarget) targetCount += 1;
    const colour = isTarget ? item.highlight_colour : item.context_colour;
    object.material = new THREE.MeshStandardMaterial({
      color: colour,
      roughness: isTarget ? 0.38 : 0.72,
      metalness: isTarget ? 0.08 : 0,
      transparent: !isTarget,
      opacity: isTarget ? 1 : 0.56,
      side: THREE.DoubleSide,
    });
  });
  if (targetCount !== 1) throw new Error(`Expected one target mesh, found ${targetCount}`);
  scene.add(loadedRoot);
  camera.position.fromArray(item.camera.position);
  camera.near = item.camera.near;
  camera.far = item.camera.far;
  camera.updateProjectionMatrix();
  controls.target.fromArray(item.camera.target);
  controls.update();
  document.documentElement.style.setProperty("--accent", item.highlight_colour);
  document.querySelector(".target-dot").style.background = item.highlight_colour;
  setDetails(item);
  status.textContent = `${label(item.change_type)} · 1 target + ${item.nodes.length - 1} bounded context`;
  window.__R4_PROOF_STATE__ = { ready: true, changeId, targetCount, nodeCount: item.nodes.length, selectedIfcRole: item.selected_ifc_role };
}

async function start() {
  const response = await fetch("../manifest.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`Manifest request failed: ${response.status}`);
  manifest = await response.json();
  manifest.scenes.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.changeId = item.change_id;
    button.innerHTML = `<strong>${label(item.change_type)}</strong><span>${item.target_global_id}</span>`;
    button.addEventListener("click", () => showChange(item.change_id).catch(fail));
    list.append(button);
  });
  const requested = new URLSearchParams(location.search).get("change_id");
  await showChange(requested || manifest.scenes[0].change_id);
}

function fail(error) {
  console.error(error);
  status.textContent = `Proof failed closed: ${error.message}`;
  window.__R4_PROOF_STATE__ = { ready: false, error: error.message, changeId: currentChangeId };
}

start().catch(fail);

