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

def sim_sobrecarga(id_no: str):
    """Simula uma sobrecarga em um nó."""
    # Simula sobrecarga de 20%
    return backend.force_overload(id_no, 0.2)

def sim_falha_no(id_no: str):
    """Simula falha em um nó removendo-o do grafo."""
    return backend.remove_node(id_no, remove_from_graph=True)

def sim_pico_consumo(id_no: str):
    """Simula pico de consumo.

    Como não temos acesso fácil aos devices para aumentar a carga real,
    vamos simular um pico forçando uma sobrecarga maior (50%).
    Isso deve disparar alertas de overload.
    """
    return backend.force_overload(id_no, 0.5)

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

@app.post("/simulation/node-failure/start")
async def start_node_failure(data: dict):
    """Inicia a simulação de falha de nó (estado)."""
    id_no = data.get("id")
    if not id_no:
        return JSONResponse({"error": "ID do nó não fornecido"}, status_code=400)

    arvore = backend.simulate_node_failure(id_no)
    return JSONResponse(arvore)

@app.post("/simulation/node-failure/end")
async def end_node_failure(data: dict):
    """Finaliza a simulação de falha de nó (restaura estado)."""
    id_no = data.get("id")
    if not id_no:
        return JSONResponse({"error": "ID do nó não fornecido"}, status_code=400)

    arvore = backend.finalize_node_failure(id_no)
    return JSONResponse(arvore)

# rota para o WebSocket de simulação
@app.websocket("/simulation")
async def simulation_socket(ws: WebSocket):
    """função que mantém streaming da árvore simulada até o cliente encerrar."""
    await ws.accept()

    try:
        # recebe parâmetros iniciais
        data = await ws.receive_text()
        data = json.loads(data)

        id_no = data.get("id")
        tipo = data.get("simulation_type")

        if not id_no or not tipo:
            await ws.send_text(json.dumps({"error": "Parâmetros insuficientes"}))
            return

        # loop que envia a nova árvore a cada segundo
        while True:
            if tipo == "overload":
                arvore = sim_sobrecarga(id_no)

            # node-failure agora é tratado via POST endpoints para estado
            # mas mantemos aqui caso o front tente usar o socket, retornando apenas snapshot atual
            elif tipo == "node-failure":
                # O front deve usar os endpoints POST para start/end.
                # Se cair aqui, mandamos snapshot atual (talvez já com falha aplicada via POST)
                arvore = backend.get_tree_snapshot()

            elif tipo == "consumption-peak":
                arvore = sim_pico_consumo(id_no)

            else:
                arvore = {"error": "Tipo de simulação inválido"}
            
            await ws.send_json(arvore)
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        print("Simulação encerrada — WebSocket desconectado.")
    except Exception as e:
        print(f"Erro na simulação: {e}")
        try:
            await ws.send_json({"error": str(e)})
        except:
            pass
    finally:
        # garante que a conexão será fechada se houver um erro antes do loop
        if ws.client_state.name == 'CONNECTED':
             await ws.close()

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

    elif data.get("add_device") is True:
        device_type_str = data.get("device_type", "GENERIC")
        try:
            dtype = DeviceType[device_type_str]
        except KeyError:
            dtype = DeviceType.GENERIC

        nova_arvore = backend.add_device(
            node_id=id_no,
            device_type=dtype,
            name=data.get("name", "Novo Dispositivo"),
            avg_power=float(data.get("avg_power", 0.1))
        )

    elif data.get("delete_device") is True:
        device_id = data.get("device_id")
        if not device_id:
             return JSONResponse({"error": "Device ID required"}, status_code=400)
        nova_arvore = backend.remove_device(
            node_id=id_no,
            device_id=device_id
        )

    elif "device_avg_power" in data:
        device_id = data.get("device_id")
        if not device_id:
             return JSONResponse({"error": "Device ID required"}, status_code=400)

        nova_arvore = backend.set_device_average_load(
            consumer_id=id_no,
            device_id=device_id,
            new_avg_power=float(data["device_avg_power"])
        )

    else:
        return JSONResponse({"error": "Nenhuma ação válida fornecida"}, status_code=400)

    if nova_arvore and "error" in nova_arvore:
         return JSONResponse(nova_arvore, status_code=400)

    return JSONResponse(nova_arvore)
