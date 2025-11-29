const icons = {
  GENERATION_PLANT: "/static/icons/substation.png",
  TRANSMISSION_SUBSTATION: "/static/icons/transmission.png",
  DISTRIBUTION_SUBSTATION: "/static/icons/distribution.png",
  CONSUMER_POINT: "/static/icons/consumer.png",
  default: "/static/icons/default.png",
};

const statusColors = {
  NORMAL: "#4CAF50",
  WARNING: "#FFC107",
  OVERLOADED: "#F44336",
  OFFLINE: "#9E9E9E",
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
  return d3
    .stratify()
    .id((d) => d.id)
    .parentId((d) => d.parent_id)(flatData);
}

export function buildTree(root, g) {
  const treeLayout = d3.tree().size([height * 0.9, width * 0.4]);
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
        .x((d) => d.y - 16)
        .y((d) => d.x)
    );

  links
    .append("text")
    .attr("class", "link-label")
    .attr("font-size", 12)
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

  // barra baseada na utilization_ratio
  // node
  //   .append("rect")
  //   .attr("class", "util-bar-bg")
  //   .attr("x", -20)
  //   .attr("y", -22)
  //   .attr("width", 40)
  //   .attr("height", 4)
  //   .attr("rx", 2)
  //   .attr("fill", "#ddd");

  // node
  //   .append("rect")
  //   .attr("class", "util-bar-fill")
  //   .attr("x", -20)
  //   .attr("y", -22)
  //   .attr("height", 4)
  //   .attr("rx", 2)
  //   .attr("width", (d) => 40 * (d.data.utilization_ratio ?? 0))
  //   .attr("fill", (d) => statusColors[d.data.status] || "#fff");

  // retângulo de fundo do ícone com cor baseada no status
  node
    .insert("rect", "image")
    .attr("x", -16)
    .attr("y", -10)
    .attr("width", 32)
    .attr("height", 26)
    .attr("rx", 6)
    .attr("fill", (d) => statusColors[d.data.status] || "#fff");

  node
    .append("image")
    .attr("href", (d) => icons[d.data.node_type] || icons.default)
    .attr("width", 22) 
    .attr("height", 22) 
    .attr("x", -12) 
    .attr("y", -10); 

  node
    .append("text")
    .attr("class", "node-text")
    .attr("dy", 24)
    .attr("text-anchor", "middle")
    .text((d) => d.data.id);
}

function formatTooltip(obj) {
  let html = `<strong>${obj.id}</strong><br>`;
  html += `<strong>Tipo:</strong> ${obj.node_type}<br>`;
  html += `<strong>Id do Cluster:</strong> ${obj.cluster_id}<br>`;
  html += `<strong>Status:</strong> ${obj.status}<br>`;
  html += `<strong>Voltagem:</strong> ${obj.nominal_voltage} V<br>`;
  html += `<strong>Capacidade:</strong> ${obj.capacity} kW<br>`;
  html += `<strong>Carga atual:</strong> ${obj.current_load} kW<br>`;

  if (Array.isArray(obj.devices) && obj.devices.length > 0) {
    html += `<br><strong>Dispositivos:</strong><br>`;
    obj.devices.forEach((device) => {
      html += `• ${device.name}<br>`;
      html += `&nbsp;&nbsp;- Carga média: ${device.average_load} kW<br>`;
      html += `&nbsp;&nbsp;- Carga atual: ${device.current_load} kW<br>`;
    }); 
  }
  return html;
}