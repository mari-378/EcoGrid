import { createSVG, buildHierarchy, buildTree } from "./js/createTree.js";
import { setupSimulation } from "./js/simulateEvent.js";
import { setupChangeNode } from "./js/changeNode.js";

const baseUrl = document.body.getAttribute("data-base-url") || "";
const btnLoadTree = document.getElementById("btn-load-tree");
const simulationForm = document.querySelector("#simulation form");
const changeForm = document.querySelector("#change-node form");

btnLoadTree.addEventListener("click", (e) => {
  const { g } = createSVG(e.target);

  fetch(`${baseUrl}/tree`, { method: "POST" })
    .then((response) => {
      if (!response.ok) {
        throw new Error("Erro ao carregar a árvore: " + response.statusText);
      }
      return response.json();
    })
    .then((data) => {
      if (data.devices) {
        data.tree.forEach((node) => {
          if (data.devices[node.id]) {
            node.devices = data.devices[node.id];
          }
        });
      }
      const root = buildHierarchy(data.tree);
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
  setupChangeNode(changeForm, baseUrl);
} else {
  console.error("Formulário de mudança de nó não encontrado.");
}
