// pegando os elementos do DOM que vou manipular
const btnLoadTree = document.getElementById("btn-load-tree");

// importação das imagens de cada tipo de nó!
const icons = {
    substation: "/static/icons/substation.png",
    transformer: "/static/icons/transformer.png",
    consumer: "/static/icons/consumer.png",
    default: "/static/icons/default.png"
};

const statusColors = {
    normal: "#4CAF50",
    warning: "#FFC107",
    overloaded: "#F44336",
    offline: "#9E9E9E",
    unknown: "#607D8B",
};

// dimensões baseadas no tamanho da tela do usuário!
const width = window.innerWidth;
const height = window.innerHeight;

const initialOffsetX = 60;

// permite o zoom para melhor visualização dos nós
const zoom = d3.zoom().scaleExtent([0.3, 3]);

function createSVG(fromButton) {
    const section = fromButton.closest("section");
    const container = d3.select(section).select(".tree-container");

    container.selectAll("svg").remove();

    const svg = container
        .append("svg")
        .attr("width", width)
        .attr("height", height)
        .call(zoom);

    const g = svg
        .append("g")
        .attr("transform", `translate(${initialOffsetX}, 0)`);

    svg.call(
        zoom.on("zoom", (e) => {
        g.attr("transform", e.transform);
        })
    );

    return { svg, g };
}

// seleciona a tooltip criada no html (para, ao passar o mouse, mostrar
// infos adicionais sobre os nós!)
const tooltip = d3.select("#tooltip");

// adicionando evento de clique ao botão que faz a árvore aparecer
btnLoadTree.addEventListener("click", (e) => {
    const { g } = createSVG(e.target);

    // carregando o json
    fetch("/static/data/tree.json")
      .then((response) => response.json())
      .then((data) => {
        const root = buildHierarchy(data);
        buildTree(root, g);
      })
      .catch((err) => console.error("Erro ao carregar JSON:", err));
});

// função para transformar o json flat recebido em uma hierarquia
function buildHierarchy(flatData) {
    const stratify = d3
        .stratify()
        .id((d) => d.id)
        .parentId((d) => d.parent_id);

    const root = stratify(flatData);

    return root;
}

// função para criar a árvore de fato, baseada nos dados fornecidos
function buildTree(root, g) {
  const treeLayout = d3.tree().size([height * 0.9, width * 0.4]); // aqui muda a distância entre os nós
  // eixo y      eixo x
  treeLayout(root);

  // limpa qualquer árvore antiga
  g.selectAll("*").remove();

  // criação dos links (ou seja, das arestas entre os nós)
  const links = g
    .selectAll(".link-group")
    .data(root.links())
    .enter()
    .append("g")
    .attr("class", "link-group");

  // path da aresta
  links
    .append("path")
    .attr("class", "link")
    .attr(
      "d",
      d3
        .linkHorizontal()
        .x((d) => d.y - 16)
        .y((d) => d.x)
    );

  // texto da resistência nas arestas
  links
    .append("text")
    .attr("class", "link-label")
    .attr("font-size", 12)
    .attr("fill", "#333")
    .attr("dy", -5)
    .text((d) => d.target.data.resistance ?? "")
    .attr("transform", function (d) {
      const x = (d.source.x + d.target.x) / 2;
      const y = (d.source.y + d.target.y) / 2;
      return `translate(${y - 16},${x})`;
    });

  // criação dos nós
  const node = g
    .selectAll(".node") // ainda não existe
    .data(root.descendants())
    .enter()
    .append("g")
    .attr("class", "node")
    .attr("transform", (d) => `translate(${d.y},${d.x})`)
    .on("mouseover", function (e, d) {
      tooltip
        .classed("hidden", false)
        .html(formatTooltip(d.data))
        .style("left", e.pageX + 15 + "px")
        .style("top", e.pageY + 15 + "px");
    })
    .on("mousemove", (e) => {
      tooltip
        .style("left", e.pageX + 15 + "px")
        .style("top", e.pageY + 15 + "px");
    })
    .on("mouseout", () => {
      tooltip.classed("hidden", true);
    });

  // adiciona as imagens para representar cada nó!
  node
    .append("image")
    .attr("href", (d) => icons[d.data.node_type] || icons.default)
    .attr("class", "node-icon")
    .attr("x", -16)
    .attr("y", -10);

  // adiciona os títulos (que serão as chaves "nome" de cada nó)
  node
    .append("text")
    .attr("class", "node-text")
    .attr("dy", 14)
    .attr("text-anchor", "middle")
    .text((d) => d.data.name);

  // retângulo de fundo (cor baseada no status)
  node
    .insert("rect", "image")
    .attr("x", -18)
    .attr("y", -12)
    .attr("width", 24)
    .attr("height", 20)
    .attr("rx", 6)
    .attr("fill", (d) => statusColors[d.data.status] || "#fff");

  // barra de fundo (base) acima do nó
  node
    .append("rect")
    .attr("class", "util-bar-bg")
    .attr("x", -20)
    .attr("y", -22)
    .attr("width", 40)
    .attr("height", 4)
    .attr("rx", 2)
    .attr("fill", "#ddd");

  // barra preenchida (proporcional + cor baseada no status)
  node
    .append("rect")
    .attr("class", "util-bar-fill")
    .attr("x", -20)
    .attr("y", -22)
    .attr("height", 4)
    .attr("rx", 2)
    .attr("width", (d) => 40 * (d.data.utilization_ratio ?? 0)) // proporção
    .attr("fill", (d) => statusColors[d.data.status] || "#fff");
}

// função que formata o tooltip, ou seja, o quadrado c/ as infos adicionais
// que aparecerão quando o mouse passa por cima!
function formatTooltip(obj) {
    let html = `<strong>${obj.name}</strong><br>`;

    html += `<strong>Id:</strong> ${obj.id}<br>`;
    html += `<strong>Status:</strong> ${obj.status}<br>`;
    html += `<strong>Tipo:</strong> ${obj.node_type}<br>`;
    html += `<strong>Capacidade:</strong> ${obj.capacity_kw} kW<br>`;
    html += `<strong>Carga atual:</strong> ${obj.current_load_kw} kW<br>`;
    html += `<strong>Utilização:</strong> ${(
        obj.utilization_ratio * 100
    ).toFixed(1)}%<br>`;

    if (obj.metadata && typeof obj.metadata === "object") {
        html += `<br><strong>Metadata:</strong><br>`;
        for (const k in obj.metadata) {
            html += ` - ${k}: ${obj.metadata[k]}<br>`;
      }
    }

    return html;
}

// lógica da seção de simulação
let socket = null;
let simulationRunning = false;

const simulationForm = document.querySelector("form");
const stopBtn = document.getElementById("stop-simulation");

simulationForm.addEventListener("submit", (e) => {
  e.preventDefault();

  if (simulationRunning) {
    alert("Simulação já está rodando!");
    return;
  }

  const chosenNode = document.querySelector("#chosen-node").value;
  const simulationChoice = document.querySelector(
    "input[name='simulation-choice']:checked"
  )?.value;

  if (!simulationChoice) {
    alert("Escolha um tipo de simulação!");
    return;
  }

  const payload = {
    id: chosenNode,
    simulation_type: simulationChoice,
  };

  // cria websocket
  socket = new WebSocket("ws://localhost:3000/ws/simulation");

  socket.onopen = () => {
    simulationRunning = true;
    socket.send(JSON.stringify(payload));
  };

  socket.onmessage = (event) => {
    const result = JSON.parse(event.data);

    // logs
    const logsContainer = document.querySelector("#simulation .logs-container");
    logsContainer.innerHTML = "<h3>Logs</h3>";

    if (Array.isArray(result.logs)) {
      result.logs.forEach((log) => {
        const p = document.createElement("p");
        p.textContent = log;
        logsContainer.appendChild(p);
      });
    }

    // renderizar árvore atualizada
    const treeContainer = document.querySelector("#simulation .tree-container");
    treeContainer.innerHTML = "";

    const { g } = createSVG(treeContainer);
    const newRoot = buildHierarchy(result.tree);
    buildTree(newRoot, g);
  };

  socket.onerror = (err) => {
    console.error("Erro WebSocket:", err);
    alert("Falha na simulação.");
  };

  socket.onclose = () => {
    simulationRunning = false;
  };
});

// botão para parar simulação
stopBtn.addEventListener("click", () => {
  if (socket) {
    socket.send(JSON.stringify({ stop: true }));
    socket.close();
  }
});

// lógica da seção de change-node
const changeForm = document.querySelector("#change-node form");

changeForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const formData = new FormData(changeForm);

  const nodeId = formData.get("node-for-change");
  const action = formData.get("opcoes");
  const newValue = formData.get("new-value");

  // o payload é montado de acordo com a ação escolhida
  const payload = { id: nodeId };

  if (action === "capacity-kw") {
    payload.capacity_kw = newValue === "" ? null : Number(newValue);
  }

  if (action === "current_load_kw") {
    payload.current_load_kw = newValue === "" ? null : Number(newValue);
  }

  if (action === "delete-node") {
    payload.delete = true;
  }

  if (action === "change-parent") {
    payload.new_parent = newValue;
  }

  try {
    const response = await fetch(`${BASE_URL}/change-node`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const result = await response.json();

    const logsContainer = document.querySelector(
      "#change-node .logs-container"
    );
    logsContainer.innerHTML = "<h3>Logs</h3>";

    if (Array.isArray(result.logs)) {
      result.logs.forEach((log) => {
        const p = document.createElement("p");
        p.textContent = log;
        logsContainer.appendChild(p);
      });
    } else {
      const p = document.createElement("p");
      p.textContent = "Nenhum log recebido.";
      logsContainer.appendChild(p);
    }

    const treeContainer = document.querySelector(
      "#change-node .tree-container"
    );
    treeContainer.innerHTML = "";

    const { g } = createSVG(treeContainer);

    const newRoot = buildHierarchy(result.tree);
    buildTree(newRoot, g);
  } catch (err) {
    console.error(err);
    alert("Erro ao aplicar alterações no nó.");
  }
});
