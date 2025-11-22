import { createSVG, buildHierarchy, buildTree } from "./js/createTree.js";
import { setupSimulation } from "./js/simulateEvent.js";
import { setupChangeNode } from "./js/changeNode.js";

const BASE_URL = document.body.getAttribute("data-base-url") || "";
const btnLoadTree = document.getElementById("btn-load-tree");
const simulationForm = document.querySelector("#simulation form");
const changeForm = document.querySelector("#change-node form");

btnLoadTree.addEventListener("click", (e) => {
  const { g } = createSVG(e.target);

  fetch(`${BASE_URL}/tree`, { method: "POST" })
    .then((response) => {
      if (!response.ok) {
        throw new Error("Erro ao carregar a árvore: " + response.statusText);
      }
      return response.json();
    })
    .then((data) => {
      const root = buildHierarchy(data);
      buildTree(root, g);
    })
    .catch((err) => console.error("Erro ao carregar a árvore:", err));
});

if (simulationForm) {
  setupSimulation(simulationForm);
} else {
  console.error("Formulário de simulação não encontrado.");
}

if (changeForm) {
  setupChangeNode(changeForm, BASE_URL);
} else {
  console.error("Formulário de mudança de nó não encontrado.");
}
