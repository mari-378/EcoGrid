from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
import json

# importa todas as funções que serão consumidas do backend
from backend.api.logical_backend_api import (
    api_get_tree_snapshot,
    api_add_node_with_routing,
    api_remove_node,
    api_change_parent_with_routing,
    api_force_change_parent,
    api_set_node_capacity,
    api_set_device_average_load, 
)

from backend.core.graph_core import PowerGridGraph
from backend.logic.bplus_index import BPlusIndex
from backend.logic.logical_graph_service import LogicalGraphService

graph = PowerGridGraph()
index = BPlusIndex()
service = LogicalGraphService(index=index, graph=graph)

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
    arvore = api_get_tree_snapshot(graph, index, service)
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

            elif tipo == "node-failure":
                arvore = sim_falha_no(id_no)

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

    if "capacity_kw" in data:
        nova_arvore = api_set_node_capacity(id_no, data["capacity_kw"])

    # elif "current_load_kw" in data:
    #     nova_arvore = alterar_carga_no(id_no, data["current_load_kw"])

    elif data.get("add_node") is True:
        nova_arvore = api_add_node_with_routing(id_no) # o id enviado aqui é o do pai!!

    elif data.get("delete_node") is True:
        nova_arvore = api_remove_node(id_no)

    elif data.get("change_parent_routing") is True:
        nova_arvore = api_change_parent_with_routing(id_no)

    elif "new_parent" in data:
        nova_arvore = api_force_change_parent(id_no, data["new_parent"])

    else:
        return JSONResponse({"error": "Nenhuma ação válida fornecida"}, status_code=400)

    if nova_arvore and "error" in nova_arvore:
         return JSONResponse(nova_arvore, status_code=400)

    return JSONResponse(nova_arvore)
