import { createSVG, buildHierarchy, buildTree } from "./createTree.js";

export function setupChangeNode(changeForm, BASE_URL) {
  changeForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const formData = new FormData(changeForm);
    const nodeId = formData.get("node-for-change"); // se eu quiser garantir que o id vá sempre maiusculo,
    const action = formData.get("opcoes");          
    const newValue = formData.get("new-value");     // então devo adicionar um ?.toUpperCase();

    if (!nodeId) return alert("O ID do nó é obrigatório.");

    const payload = { id: nodeId };

    if (action === "capacity-kw") {
      const value = Number(newValue);
      if (isNaN(value)) return alert("Capacidade deve ser um número.");
      payload.capacity_kw = value;

    // } else if (action === "current_load_kw") {
    //   const value = Number(newValue);
    //   if (isNaN(value)) return alert("Carga atual deve ser um número.");
    //   payload.current_load_kw = value;

    } else if (action === "add-node") {
      payload.add_node = true;

    } else if (action === "delete-node") {
      payload.delete_node = true;

    } else if (action === "change-parent") {
      if (!newValue) return alert("O novo pai deve ter um ID.");
      payload.new_parent = newValue;
      
    } else if (action === "change-parent-routing") {
      payload.change_parent_routing = true;

    } else {
      return alert("Nenhuma ação válida selecionada.");
    }

    try {
      const response = await fetch(`${BASE_URL}/change-node`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const result = await response.json();

      if (!response.ok) {
        alert(
          `Erro ${response.status}: ${
            result.error || "Erro desconhecido ao aplicar alterações."
          }`
        );
        return;
      }

      const logsContainer = document.querySelector(
        "#change-node .logs-container"
      );
      logsContainer.innerHTML = "<h3>Logs</h3>";

      result.logs?.forEach((log) => {
        const p = document.createElement("p");
        p.textContent = log;
        logsContainer.appendChild(p);
      });

      const treeContainer = document.querySelector(
        "#change-node .tree-container"
      );

      const { g } = createSVG(treeContainer);
      const newRoot = buildHierarchy(result.tree);
      buildTree(newRoot, g);
    } catch (err) {
      console.error(err);
      alert("Erro ao aplicar alterações no nó. Verifique o console.");
    }
  });
}
