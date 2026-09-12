import * as THREE from "./vendor/three.module.js";
import { GLTFLoader } from "./vendor/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "./vendor/addons/controls/OrbitControls.js";
import { createReferenceGrid } from "./reference_grid.js";

const canvas = document.querySelector("#viewer");
const status = document.querySelector("#status");
const list = document.querySelector("#change-list");
const details = document.querySelector("#details");
const params = new URLSearchParams(location.search);
const embedded = params.get("embedded") === "1";
if (embedded) document.body.classList.add("embedded");
let language = params.get("lang") || "en";
let active = true;
let frame = 0;
let generation = 0;
let loadedRoot = null;
let currentItem = null;
let currentManifest = null;
let currentManifestUrl = null;
let currentRequestId = null;
let pendingProof = null;
let faded = true;
let referenceGrid = null;
const roots = new Map();
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
renderer.outputColorSpace = THREE.SRGBColorSpace;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x000000);
const camera = new THREE.PerspectiveCamera(42, 1, 0.01, 1000);
camera.up.set(0, 0, 1);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.12;
scene.add(new THREE.HemisphereLight(0xffffff, 0x657382, 2.0));
const sun = new THREE.DirectionalLight(0xffffff, 2.0);
sun.position.set(8, -10, 14);
scene.add(sun);
window.__R4_RENDER_COUNT__ = 0;

function render() {
  frame = 0;
  if (!active || document.hidden) return;
  const width = Math.max(canvas.clientWidth, 1);
  const height = Math.max(canvas.clientHeight, 1);
  const ratio = renderer.getPixelRatio();
  if (canvas.width !== Math.floor(width * ratio) || canvas.height !== Math.floor(height * ratio)) {
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }
  controls.update();
  renderer.render(scene, camera);
  window.__R4_RENDER_COUNT__ += 1;
  if (pendingProof) {
    window.__R4_PROOF_STATE__ = pendingProof;
    pendingProof = null;
  }
}
function requestRender() {
  if (!frame && active && !document.hidden) frame = requestAnimationFrame(render);
}
controls.addEventListener("change", requestRender);
new ResizeObserver(requestRender).observe(canvas);
document.addEventListener("visibilitychange", requestRender);
window.setActive = (value) => {
  active = Boolean(value);
  if (!active && frame) { cancelAnimationFrame(frame); frame = 0; }
  if (active) requestRender();
};

function t(zh, en) { return language === "zh_CN" ? zh : en; }
function label(type) {
  const labels = {
    deleted: ["删除", "Deleted"], added: ["新增", "Added"],
    property_modified: ["属性修改", "Property modified"],
    geometry_modified: ["几何修改", "Geometry modified"],
    relationship_modified: ["关系修改", "Relationship modified"],
  };
  return labels[type] ? t(...labels[type]) : type;
}
function updateText() {
  document.documentElement.lang = language === "zh_CN" ? "zh-CN" : "en";
  document.querySelector("#heading").textContent = t("局部三维", "Local 3D");
  document.querySelector("#boundary").textContent = t(
    "按 IFC 原始形状高亮变化构件。周围构件仅供定位，变更详情以报告为准。",
    "Changes highlighted on the actual IFC geometry. Nearby elements provide context; the report remains the fact source.");
  document.querySelector("#focus").textContent = t("定位构件", "Focus element");
  document.querySelector("#fit").textContent = t("查看周围", "Fit context");
  document.querySelector("#fade").textContent = faded ? t("周围淡化", "Context faded") : t("周围实体", "Context solid");
  document.querySelector("#legend-target").textContent = t("变化构件", "Changed element");
  document.querySelector("#legend-context").textContent = t("周围构件", "Nearby elements");
  const gridLabel = document.querySelector("#grid-scale");
  gridLabel.textContent = referenceGrid ? t(
    `参考网格 · ${referenceGrid.userData.referenceGrid.spacingM} m`,
    `Reference grid · ${referenceGrid.userData.referenceGrid.spacingM} m`) : "";
  gridLabel.title = t("水平视觉参考，不代表建筑楼层或结构轴网。", "Horizontal visual reference, not a building floor or structural axis grid.");
  document.querySelector("#hint").textContent = t("拖动旋转 · 滚轮缩放 · 右键拖动平移", "Drag to orbit · Scroll to zoom · Right-drag to pan");
  if (currentItem) {
    status.textContent = t(
      label(currentItem.change_type) + " · " + (currentItem.selected_ifc_role === "source" ? "旧版" : "新版") + " · 原始构件形状",
      label(currentItem.change_type) + " · 1 target + " + (currentItem.nodes.length - 1) + " bounded context");
    setDetails(currentItem);
    buildList();
  }
}
window.setLanguage = (value) => { language = value; updateText(); };
function setDetails(item) {
  const target = item.nodes.find((node) => node.role === "target");
  const rows = [
    [t("构件", "Element"), target.entity_type],
    [t("楼层", "Storey"), target.storey_name || "—"],
    ["GlobalId", item.target_global_id],
    [t("模型版本", "Model version"), item.selected_ifc_role === "source" ? t("旧版", "Source") : t("新版", "Revised")],
  ];
  details.replaceChildren(...rows.flatMap(([term, value]) => {
    const dt = document.createElement("dt"), dd = document.createElement("dd");
    dt.textContent = term; dd.textContent = value;
    return [dt, dd];
  }));
}
function buildList() {
  list.replaceChildren();
  currentManifest.scenes.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.changeId = item.change_id;
    button.setAttribute("aria-pressed", String(item === currentItem));
    const strong = document.createElement("strong"), span = document.createElement("span");
    strong.textContent = label(item.change_type); span.textContent = item.target_global_id;
    button.append(strong, span);
    button.addEventListener("click", () => showChange(item, currentManifestUrl, currentRequestId).catch(fail));
    list.append(button);
  });
}
function disposeRoot(root) {
  root.traverse((object) => {
    object.geometry?.dispose();
    if (Array.isArray(object.material)) object.material.forEach((material) => material.dispose());
    else object.material?.dispose();
  });
}
window.clearScene = (loading = false) => {
  generation += 1;
  if (loadedRoot) scene.remove(loadedRoot);
  if (referenceGrid) { scene.remove(referenceGrid); disposeRoot(referenceGrid); referenceGrid = null; }
  window.__R4_GRID_STATE__ = null;
  document.querySelector("#grid-scale").textContent = "";
  loadedRoot = currentItem = null;
  pendingProof = null;
  window.__R4_PROOF_STATE__ = { ready: false };
  status.textContent = loading ? t("正在准备所选构件…", "Preparing selected element…") : t("请选择变更记录", "Select a change record");
  details.replaceChildren();
  list.replaceChildren();
  requestRender();
};
function fit(targetOnly) {
  if (!loadedRoot || !currentItem) return;
  const box = new THREE.Box3();
  loadedRoot.traverse((object) => {
    if (object.isMesh && (!targetOnly || object.userData.role === "target")) box.expandByObject(object);
  });
  const centre = box.getCenter(new THREE.Vector3());
  const radius = Math.max(box.getSize(new THREE.Vector3()).length() / 2, 0.3);
  const aspect = Math.max(canvas.clientWidth / Math.max(canvas.clientHeight, 1), 0.1);
  const verticalHalf = THREE.MathUtils.degToRad(camera.fov / 2);
  const limitingHalf = Math.min(verticalHalf, Math.atan(Math.tan(verticalHalf) * aspect));
  const distance = radius / Math.sin(limitingHalf) * 1.12;
  camera.position.copy(centre).addScaledVector(new THREE.Vector3(1.15, -1.35, 0.9).normalize(), distance);
  camera.near = Math.max(distance / 10000, 0.001);
  camera.far = Math.max(distance * 20, currentItem.camera.far, 50);
  controls.target.copy(centre);
  controls.minDistance = Math.max(radius * 0.08, 0.02);
  controls.maxDistance = camera.far * 0.75;
  camera.updateProjectionMatrix();
  // Discard residual orbit momentum when fitting a different element.
  const damping = controls.enableDamping;
  controls.enableDamping = false; controls.update(); controls.enableDamping = damping;
  requestRender();
}
function rootBytes(root) {
  let bytes = 0;
  root.traverse((object) => {
    if (!object.geometry) return;
    Object.values(object.geometry.attributes).forEach((attribute) => { bytes += attribute.array.byteLength; });
    bytes += object.geometry.index?.array.byteLength || 0;
  });
  return bytes;
}
function updateContext() {
  if (loadedRoot) loadedRoot.traverse((object) => {
    if (object.isMesh && object.userData.role === "context") {
      object.material.transparent = faded;
      object.material.opacity = faded ? 0.28 : 1;
      object.material.depthWrite = !faded;
      object.material.needsUpdate = true;
    }
  });
  document.querySelector("#fade").setAttribute("aria-pressed", String(faded));
  updateText();
  requestRender();
}
document.querySelector("#focus").addEventListener("click", () => fit(true));
document.querySelector("#fit").addEventListener("click", () => fit(false));
document.querySelector("#fade").addEventListener("click", () => { faded = !faded; updateContext(); });

async function showChange(item, manifestUrl, requestId) {
  window.clearScene(true);
  const ownGeneration = generation;
  const url = new URL(item.file, manifestUrl);
  if (url.origin !== location.origin || !url.pathname.startsWith(new URL("../", location.href).pathname)) throw new Error("Scene outside local session");
  const key = url.href + ":" + item.sha256;
  let root = roots.get(key);
  if (!root) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error("Scene unavailable");
    const bytes = await response.arrayBuffer();
    const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
      (value) => value.toString(16).padStart(2, "0")).join("");
    if (digest !== item.sha256) throw new Error("Scene digest mismatch");
    if (generation !== ownGeneration) return;
    const gltf = await new GLTFLoader().parseAsync(bytes, new URL(".", url).href);
    root = gltf.scene;
    if (generation !== ownGeneration) { disposeRoot(root); return; }
    const ids = [];
    let targetCount = 0;
    root.traverse((object) => {
      if (!object.isMesh) return;
      const id = object.userData.global_id;
      const expected = item.nodes.find((node) => node.global_id === id);
      if (!expected || expected.role !== object.userData.role || object.userData.ifc_role !== item.selected_ifc_role)
        throw new Error("Scene metadata mismatch");
      const isTarget = id === item.target_global_id && object.userData.role === "target";
      if (isTarget) targetCount += 1;
      ids.push(id);
      object.material.dispose();
      object.material = new THREE.MeshStandardMaterial({
        color: isTarget ? item.highlight_colour : item.context_colour,
        roughness: 0.85, metalness: 0, flatShading: true,
        side: THREE.DoubleSide,
        polygonOffset: isTarget, polygonOffsetFactor: 1, polygonOffsetUnits: 1,
      });
    });
    if (targetCount !== 1 || ids.length !== item.nodes.length || new Set(ids).size !== ids.length) {
      disposeRoot(root); throw new Error("Scene identity is not unique");
    }
    const targetMeshes = [];
    root.traverse((object) => { if (object.isMesh && object.userData.role === "target") targetMeshes.push(object); });
    targetMeshes.forEach((object) => {
      // Contour edges come from the actual mesh, never a bounding-box proxy.
      if (object.geometry.index?.count <= 240000) {
        const edges = new THREE.LineSegments(
          new THREE.EdgesGeometry(object.geometry, 30),
          new THREE.LineBasicMaterial({ color: 0x302e2c, transparent: true, opacity: 0.55 }));
        object.add(edges);
      }
    });
    roots.set(key, root);
    let retainedBytes = [...roots.values()].reduce((sum, candidate) => sum + rootBytes(candidate), 0);
    while (roots.size > 8 || (roots.size > 1 && retainedBytes > 64 * 1024 * 1024)) {
      const oldest = roots.keys().next().value;
      retainedBytes -= rootBytes(roots.get(oldest));
      disposeRoot(roots.get(oldest)); roots.delete(oldest);
    }
  } else {
    roots.delete(key); roots.set(key, root);
  }
  if (generation !== ownGeneration) return;
  loadedRoot = root; currentItem = item; currentRequestId = requestId;
  scene.add(root);
  referenceGrid = createReferenceGrid(new THREE.Box3().setFromObject(root));
  scene.add(referenceGrid);
  window.__R4_GRID_STATE__ = referenceGrid.userData.referenceGrid;
  document.querySelector(".target-dot").style.background = item.highlight_colour;
  updateContext();
  fit(false);
  // The native pane only signals scene_loaded after an actual render.
  pendingProof = {
      ready: true, requestId, changeId: item.change_id, targetGlobalId: item.target_global_id,
      targetCount: 1, nodeCount: item.nodes.length, selectedIfcRole: item.selected_ifc_role,
  };
  requestRender();
}
function fail(error) {
  window.clearScene();
  status.textContent = t("场景无法验证，请重新分析。", "Scene could not be verified. Run the analysis again.");
  window.__R4_PROOF_STATE__ = { ready: false, error: String(error.message), requestId: currentRequestId };
}
window.loadManifest = async (url, requestId) => {
  window.clearScene(true);
  currentRequestId = requestId;
  const ownGeneration = generation;
  try {
    const manifestUrl = new URL(url, location.href);
    const response = await fetch(manifestUrl, { cache: "no-store" });
    if (!response.ok) throw new Error("Manifest unavailable");
    const manifest = await response.json();
    if (generation !== ownGeneration) return;
    if (!manifest.scenes?.length) throw new Error("No scene");
    currentManifest = manifest; currentManifestUrl = manifestUrl;
    const requested = params.get("change_id");
    const item = manifest.scenes.find((candidate) => candidate.change_id === requested) || manifest.scenes[0];
    await showChange(item, manifestUrl, requestId);
  } catch (error) {
    if (currentRequestId === requestId) fail(error);
  }
};
updateText();
window.__R4_SHELL_READY__ = true;
window.clearScene();
if (!embedded) window.loadManifest(new URL("../manifest.json", location.href).href, 0);
