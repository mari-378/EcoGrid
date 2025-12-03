const icons = {
  GENERATION_PLANT: "/static/icons/substation.png",
  TRANSMISSION_SUBSTATION: "/static/icons/transmission.png",
  DISTRIBUTION_SUBSTATION: "/static/icons/distribution.png",
  CONSUMER_POINT: "/static/icons/consumer.png",
  "Usina Geradora": "/static/icons/substation.png",
  "Subestação de Transmissão": "/static/icons/transmission.png",
  "Subestação de Distribuição": "/static/icons/distribution.png",
  Consumidor: "/static/icons/consumer.png",
  default: "/static/icons/default.png",
};

const statusColors = {
  NORMAL: "#4CAF50",
  WARNING: "#FFC107",
  OVERLOADED: "#F44336",
  OFFLINE: "#9E9E9E",
  Normal: "#4CAF50",
  Alerta: "#FFC107",
  Sobrecarga: "#F44336",
  "Sem Energia": "#9E9E9E",
  Falha: "#000000",
  Desconhecido: "#607D8B",
  unknown: "#607D8B",
};

const width = window.innerWidth;
const height = window.innerHeight;
const initialOffsetX = 60;

export const zoom = d3.zoom().scaleExtent([0.3, 3]);
export const tooltip = d3.select("#tooltip");

export function createSVG(fromButton) {
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

  svg.call(zoom.on("zoom", (e) => g.attr("transform", e.transform)));

  return { svg, g };
}

export function buildHierarchy(flatData) {
  const roots = flatData.filter((d) => d.parent_id === null);

  if (roots.length > 1) {
    const virtualRoot = {
      id: "virtual_root",
      parent_id: null,
      node_type: "default",
      status: "Normal",
    };

    const modifiedData = flatData.map((d) => {
      if (d.parent_id === null) {
        return { ...d, parent_id: "virtual_root" };
      }
      return d;
    });

    modifiedData.push(virtualRoot);

    return d3
      .stratify()
      .id((d) => d.id)
      .parentId((d) => d.parent_id)(modifiedData);
  }

  return d3
    .stratify()
    .id((d) => d.id)
    .parentId((d) => d.parent_id)(flatData);
}

export function buildTree(root, g) {
  const treeLayout = d3.tree().size([height * 1.8, width * 0.4]);
  treeLayout(root);

  g.selectAll("*").remove();

  // links (arestas)
  const links = g
    .selectAll(".link-group")
    .data(root.links())
    .enter()
    .append("g")
    .attr("class", "link-group");

  links
    .append("path")
    .attr("class", "link")
    .attr(
      "d",
      d3
        .linkHorizontal()
        .x((d) => d.y - 8)
        .y((d) => d.x)
    );

  links
    .append("text")
    .attr("class", "link-label")
    .attr("font-size", 10)
    .attr("dy", -5)
    .text((d) => d.target.data.resistance ?? "")
    .attr("transform", (d) => {
      const x = (d.source.x + d.target.x) / 2;
      const y = (d.source.y + d.target.y) / 2;
      return `translate(${y - 20},${x})`;
    });

  // nodes (vértices)
  const node = g
    .selectAll(".node")
    .data(root.descendants())
    .enter()
    .append("g")
    .attr("class", "node")
    .attr("transform", (d) => `translate(${d.y},${d.x})`)
    .on("mouseover", (e, d) => {
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
    .on("mouseout", () => tooltip.classed("hidden", true));

  node
    .insert("rect", "image")
    .attr("x", -8)
    .attr("y", -6)
    .attr("width", 16)
    .attr("height", 14)
    .attr("rx", 6)
    .attr("fill", (d) => statusColors[d.data.status] || statusColors.unknown);

  node
    .append("image")
    .attr("href", (d) => icons[d.data.node_type] || icons.default)
    .attr("width", 12)
    .attr("height", 12)
    .attr("x", -6)
    .attr("y", -5);

  node
    .append("text")
    .attr("class", "node-text")
    .attr("dy", 14)
    .attr("text-anchor", "middle")
    .text((d) => d.data.id);
}

function formatTooltip(obj) {
  let html = `<strong>${obj.id}</strong><br>`;
  html += `<strong>Tipo:</strong> ${obj.node_type}<br>`;

  if (obj.cluster_name) {
    html += `<strong>Nome da Cidade:</strong> ${obj.cluster_name}<br>`;
  } else if (obj.cluster_id !== null && obj.cluster_id !== undefined) {
    html += `<strong>Id do Cluster:</strong> ${obj.cluster_id}<br>`;
  }

  if (obj.status) {
    html += `<strong>Status:</strong> ${obj.status}<br>`;
  }

  if (obj.nominal_voltage) {
    html += `<strong>Tensão:</strong> ${obj.nominal_voltage} V<br>`;
  }

  if (obj.capacity !== null && obj.capacity !== undefined) {
    html += `<strong>Capacidade:</strong> ${obj.capacity} kW<br>`;
  }

  if (obj.current_load !== null && obj.current_load !== undefined) {
    html += `<strong>Carga atual:</strong> ${obj.current_load} kW<br>`;
  }

  if (obj.energy_loss !== null && obj.energy_loss !== undefined) {
    html += `<strong>Perca de energia:</strong> ${obj.energy_loss}%<br>`;
  }

  if (Array.isArray(obj.devices) && obj.devices.length > 0) {
    html += `<br><strong>Dispositivos:</strong><br>`;
    obj.devices.forEach((device) => {
      html += `• ${device.name}<br>`;
      html += `&nbsp;&nbsp;- Potência Média: ${device.avg_power} kW<br>`;
      html += `&nbsp;&nbsp;- Potência Atual: ${device.current_power} kW<br>`;
    });
  }
  return html;
}
