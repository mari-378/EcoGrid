from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
import json
import uuid
import sys
import os

# Garante que os módulos do backend possam ser importados da raiz
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from api.backend_facade import PowerGridBackend
from core.models import Node, Edge, NodeType, EdgeType
from backend.physical.device_model import DeviceType
from grid_generation import generate_default_graph

# Caminhos dos arquivos de grafo
NODES_PATH = "backend/out/nodes"
EDGES_PATH = "backend/out/edges"

# Gera o grafo sempre que o aplicativo inicia
generate_default_graph(nodes_path=NODES_PATH, edges_path=EDGES_PATH)

# Inicializa o BackendFacade
# Isso lida com o carregamento do grafo a partir de arquivos e configuração do índice/serviço
# Use NODES_PATH as the first argument (config_or_path)
backend = PowerGridBackend(config_or_path=NODES_PATH, edges_path=EDGES_PATH)

# configuração do FastAPI
app = FastAPI()

# configuração dos diretórios de arquivos estáticos e templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    '''função que renderiza o template HTML principal'''
    # adicionando a URL base no contexto para uso no JS
    base_url = f"http://{request.url.netloc}"
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "base_url": base_url}
    )

@app.post("/tree")
async def get_tree():
    """função que retorna a árvore completa inicial."""
    arvore = backend.get_tree_snapshot()
    return JSONResponse(arvore)

# rota para alterar atributos de um nó específico
@app.post("/change-node")
async def change_node(data: dict):
    """função que altera atributos de um nó específico."""
    id_no = data.get("id")
    if not id_no:
        return JSONResponse({"error": "ID do nó não fornecido"}, status_code=400)

    nova_arvore = None

    if "capacity" in data:
        nova_arvore = backend.set_node_capacity(id_no, data["capacity"])

    elif data.get("add_node") is True:
        # Lógica para adicionar um novo nó conectado ao id_no (pai)
        new_node_id = str(uuid.uuid4())[:8]

        # Precisamos de uma posição. Vamos pegar a posição do pai e deslocar um pouco.
        parent_node = backend.graph.get_node(id_no)
        pos_x = 0.0
        pos_y = 0.0
        if parent_node:
            pos_x = parent_node.position_x + 10 # deslocamento arbitrário
            pos_y = parent_node.position_y + 10

        new_node = Node(
            id=new_node_id,
            node_type=NodeType.CONSUMER_POINT,
            position_x=pos_x,
            position_y=pos_y,
            nominal_voltage=127.0, # padrão
            capacity=50.0, # padrão
            current_load=0.0
        )

        # Cria aresta conectando pai ao novo nó
        new_edge = Edge(
            id=f"edge_{id_no}_{new_node_id}",
            edge_type=EdgeType.LV_DISTRIBUTION_SEGMENT, # Assumindo baixa tensão para consumidor
            from_node_id=id_no,
            to_node_id=new_node_id,
            length=10.0 # arbitrário
        )

        nova_arvore = backend.add_node_with_routing(new_node, [new_edge])

    elif data.get("delete_node") is True:
        nova_arvore = backend.remove_node(id_no)

    elif data.get("change_parent_routing") is True:
        nova_arvore = backend.change_parent_with_routing(id_no)

    elif "new_parent" in data:
        nova_arvore = backend.force_change_parent(id_no, data["new_parent"])

    else:
        return JSONResponse({"error": "Nenhuma ação válida fornecida"}, status_code=400)

    if nova_arvore and "error" in nova_arvore:
         return JSONResponse(nova_arvore, status_code=400)

    return JSONResponse(nova_arvore)
