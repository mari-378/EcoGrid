import { createSVG, buildHierarchy, buildTree } from "./createTree.js";

let socket = null;
let simulationRunning = false;

export function setupSimulation(simulationForm) {
  const stopBtn = document.getElementById("stop-simulation");

  simulationForm.addEventListener("submit", (e) => {
    e.preventDefault();

    if (simulationRunning) return alert("Simulação já está rodando!");

    const chosenNode = document.querySelector("#chosen-node").value;
    const simulationChoice = document.querySelector(
      "input[name='simulation-choice']:checked"
    )?.value;

    if (!chosenNode || !simulationChoice) {
      return alert("Preencha o ID do nó e escolha o tipo de simulação.");
    }

    const payload = { id: chosenNode, simulation_type: simulationChoice };

    socket = new WebSocket("ws://localhost:8000/simulation");

    socket.onopen = () => {
      simulationRunning = true;
      socket.send(JSON.stringify(payload));
    };

    socket.onmessage = (event) => {
      const result = JSON.parse(event.data);

      if (result.error) {
        alert("Erro na simulação: " + result.error);
        socket.close();
        return;
      }

      const logsContainer = document.querySelector(
        "#simulation .logs-container"
      );
      logsContainer.innerHTML = "<h3>Logs</h3>";

      result.logs?.forEach((log) => {
        const p = document.createElement("p");
        p.textContent = log;
        logsContainer.appendChild(p);
      });

      const treeContainer = document.querySelector(
        "#simulation .tree-container"
      );
      const { g } = createSVG(treeContainer);
      const newRoot = buildHierarchy(result.tree);
      buildTree(newRoot, g);
    };

    socket.onclose = () => {
      simulationRunning = false;
      console.log("WebSocket de simulação desconectado.");
    };

    socket.onerror = (error) => {
      console.error("Erro no WebSocket:", error);
      alert("Erro na conexão WebSocket. Verifique o console.");
      simulationRunning = false;
    };
  });

  stopBtn.addEventListener("click", () => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.close();
    }
  });
}
