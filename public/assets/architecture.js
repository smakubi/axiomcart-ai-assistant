import { highlightPython } from "./python-highlight.js?v=20260802-8";

const elements = {
  voicePipeline: document.querySelector("#voice-pipeline"),
  componentList: document.querySelector("#component-list"),
  sourceConcept: document.querySelector("#source-concept"),
  sourceTitle: document.querySelector("#source-title"),
  sourcePath: document.querySelector("#source-path"),
  sourceRole: document.querySelector("#source-role"),
  sourceCode: document.querySelector("#source-code"),
  copySource: document.querySelector("#copy-source"),
};

let manifest;
let selectedComponent;

function escapeHtml(value) {
  return value.replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}

function renderVoicePipeline(stages) {
  elements.voicePipeline.innerHTML = stages.map((stage, index) => `
    <article>
      <span>${String(index + 1).padStart(2, "0")}</span>
      <h3>${escapeHtml(stage.title)}</h3>
      <p>${escapeHtml(stage.detail)}</p>
      <code>${escapeHtml(stage.technology)}</code>
    </article>
    ${index < stages.length - 1 ? '<i aria-hidden="true">→</i>' : ""}
  `).join("");
}

function selectComponent(componentId, { updateHash = true } = {}) {
  const component = manifest.components.find((item) => item.id === componentId) || manifest.components[0];
  selectedComponent = component;
  document.querySelectorAll("[data-component]").forEach((button) => {
    button.dataset.selected = String(button.dataset.component === component.id);
  });
  elements.sourceConcept.textContent = component.concept;
  elements.sourceTitle.textContent = component.title;
  elements.sourcePath.textContent = component.path;
  elements.sourceRole.textContent = component.role;
  elements.sourceCode.innerHTML = highlightPython(component.source);
  if (updateHash) history.replaceState(null, "", `#${component.id}`);
}

function renderComponents(components) {
  elements.componentList.innerHTML = components.map((component) => `
    <button type="button" data-component="${escapeHtml(component.id)}">
      <strong>${escapeHtml(component.title)}</strong>
      <span>${escapeHtml(component.path)}</span>
    </button>
  `).join("");
}

async function loadArchitecture() {
  const response = await fetch("/api/architecture", { cache: "no-store" });
  if (!response.ok) throw new Error("Architecture data is unavailable.");
  manifest = await response.json();
  renderVoicePipeline(manifest.voice_pipeline);
  renderComponents(manifest.components);
  const initialId = location.hash.slice(1) || "graph";
  selectComponent(initialId, { updateHash: false });
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-component]");
  if (button && manifest) selectComponent(button.dataset.component);
});

document.addEventListener("keydown", (event) => {
  const component = event.target.closest("[data-component][role='button']");
  if (component && (event.key === "Enter" || event.key === " ")) {
    event.preventDefault();
    selectComponent(component.dataset.component);
  }
});

elements.copySource.addEventListener("click", async () => {
  if (!selectedComponent) return;
  await navigator.clipboard.writeText(selectedComponent.source);
  elements.copySource.textContent = "Copied";
  setTimeout(() => { elements.copySource.textContent = "Copy"; }, 1200);
});

loadArchitecture().catch((error) => {
  elements.sourceRole.textContent = error.message;
});
