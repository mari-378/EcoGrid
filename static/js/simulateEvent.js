import { createSVG, buildHierarchy, buildTree } from "./createTree.js";

let socket = null;
let simulationRunning = false;

export function setupSimulation(simulationForm) {
  const stopBtn = document.getElementById("stop-simulation");
  let lastSimulationType = null;
  let lastNodeId = null;

  simulationForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (simulationRunning) return alert("Simulação já está rodando!");

    const chosenNode = document.querySelector("#chosen-node").value;
    const simulationChoice = document.querySelector(
      "input[name='simulation-choice']:checked"
    )?.value;

    if (!chosenNode || !simulationChoice) {
      return alert("Preencha o ID do nó e escolha o tipo de simulação.");
    }

    lastSimulationType = simulationChoice;
    lastNodeId = chosenNode;
    simulationRunning = true; // Set running flag

    if (simulationChoice === "node-failure") {
      // Logic for Node Failure using POST
      try {
        const response = await fetch("/simulation/node-failure/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: chosenNode })
        });
        const result = await response.json();
        handleSimulationUpdate(result);
        // Note: For node failure, we don't open a socket loop,
        // but we keep simulationRunning=true to allow "Finalizar" to work.
      } catch (error) {
        console.error("Erro na simulação de falha:", error);
        alert("Erro ao iniciar falha de nó.");
        simulationRunning = false;
      }
      return;
    }

    // Existing WebSocket logic for other simulations
    const payload = { id: chosenNode, simulation_type: simulationChoice };

    socket = new WebSocket("ws://localhost:8000/simulation");

    socket.onopen = () => {
      // simulationRunning is already true
      socket.send(JSON.stringify(payload));
    };

    socket.onmessage = (event) => {
      const result = JSON.parse(event.data);
      handleSimulationUpdate(result);
    };

    socket.onclose = () => {
      // Only set to false if it wasn't a manual stop of node-failure
      if (lastSimulationType !== "node-failure") {
          simulationRunning = false;
      }
      console.log("WebSocket de simulação desconectado.");
    };

    socket.onerror = (error) => {
      console.error("Erro no WebSocket:", error);
      alert("Erro na conexão WebSocket. Verifique o console.");
      simulationRunning = false;
    };
  });

  stopBtn.addEventListener("click", async () => {
    if (lastSimulationType === "node-failure" && simulationRunning) {
        try {
            const response = await fetch("/simulation/node-failure/end", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id: lastNodeId })
            });
            const result = await response.json();
            handleSimulationUpdate(result);
            alert("Simulação de falha finalizada.");
        } catch (error) {
            console.error("Erro ao finalizar falha:", error);
        }
        simulationRunning = false;
        lastSimulationType = null;
        lastNodeId = null;
    }
    else if (socket && socket.readyState === WebSocket.OPEN) {
      socket.close();
      simulationRunning = false;
      lastSimulationType = null;
    }
  });
}

function handleSimulationUpdate(result) {
    if (result.error) {
        alert("Erro na simulação: " + result.error);
        if (socket) socket.close();
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
}
