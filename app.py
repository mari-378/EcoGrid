from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
import json

# trocar depois para as funções reais do projeto!!! TEMPORÁRIO 
from tree import (
    get_initial_tree,
    alterar_capacidade_no,
    alterar_carga_no,
    deletar_no,
    alterar_pai_no
)

# trocar depois para as funções reais do projeto!!! TEMPORÁRIO 
from simulation import (
    sim_sobrecarga,
    sim_falha_no,
    sim_pico_consumo
)

# configuração do FastAPI
app = FastAPI()

# configuração dos diretórios de arquivos estáticos e templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# rota principal que renderiza o template HTML
@app.get("/")
def home(request: Request):
    '''função que renderiza o template HTML principal'''
    return templates.TemplateResponse("index.html", {"request": request})

# rota para enviar a árvore inicial
@app.post("/tree")
async def tree():
    """função que retorna a árvore completa inicial."""
    arvore = get_initial_tree()
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

# rota para alterar atributos de um nó específico
@app.post("/change-node")
async def change_node(data: dict):
    """função que altera atributos de um nó específico."""
    id_no = data.get("id")
    if not id_no:
        return JSONResponse({"error": "ID do nó não fornecido"}, status_code=400)

    if "capacity_kw" in data:
        nova_arvore = alterar_capacidade_no(id_no, data["capacity_kw"])

    elif "current_load_kw" in data:
        nova_arvore = alterar_carga_no(id_no, data["current_load_kw"])

    elif "delete_node" in data:
        nova_arvore = deletar_no(id_no)

    elif "new_parent" in data:
        nova_arvore = alterar_pai_no(id_no, data["new_parent"])

    else:
        return JSONResponse({"error": "Nenhuma ação válida fornecida"}, status_code=400)

    return JSONResponse(nova_arvore)
