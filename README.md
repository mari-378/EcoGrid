## 🌐 EcoGrid+: Plataforma Inteligente para Redes de Energia Sustentáveis

O **EcoGrid+** é uma plataforma de visualização e simulação de redes de distribuição elétrica. Ele permite o gerenciamento e a alteração de parâmetros (capacidade, carga) de nós (subestações, transformadores e consumidores) e a visualização em tempo real do status (Normal, Aviso, Sobrecarga) através de uma interface interativa baseada em árvores D3.js. É ideal para testar cenários de carga e falhas.

## 🛠️ Tecnologias Utilizadas

O projeto EcoGrid é um *stack* completo (Full Stack) que combina um *backend* robusto em Python com uma interface de visualização dinâmica em JavaScript.

  * **Python:** Linguagem de programação principal do *backend*.
  * **FastAPI:** Framework moderno e rápido para construir a API que gerencia o estado da árvore e executa as simulações.
  * **Uvicorn:** Servidor ASGI para rodar a aplicação FastAPI.
  * **Jinja2:** Usado pelo FastAPI para renderizar os templates HTML.
  * **D3.js (Data-Driven Documents):** Biblioteca JavaScript utilizada para a **visualização interativa da árvore** (layout hierárquico, nós, links, zoom/pan).
  * **JavaScript (ES Modules):** Usado no *frontend* para comunicação via **Fetch API** (para modificações de nó) e **WebSockets** (para simulações em tempo real).

-----

## 🚀 Instalação e Configuração

Siga os passos abaixo para colocar o EcoGrid para rodar em seu ambiente local.

### 1\. Clonar o Repositório

Abra seu terminal ou prompt de comando e clone o projeto. **Ajuste o caminho do repositório se necessário.**

```bash
git clone https://github.com/mari-378/EcoGrid.git
cd EcoGrid
```

Abra o projeto em sua IDE (Ambiente de Desenvolvimento Integrado) preferida. Por exemplo, se estiver usando o VS Code, digite:

```bash
code .
```

### 2\. Configurar o Ambiente Virtual

Crie um ambiente virtual para isolar as dependências do projeto.

| Sistema Operacional | Comando para Criar Ambiente |
| :--- | :--- |
| Windows | `python -m venv venv` |
| Linux/macOS | `python3 -m venv venv` |

### 3\. Ativar o Ambiente Virtual

Ative o ambiente virtual para que as bibliotecas sejam instaladas no local correto.

| Sistema Operacional | Comando para Ativar Ambiente |
| :--- | :--- |
| Windows | `venv\Scripts\activate` |
| Linux/macOS | `source venv/bin/activate` |

### 4\. Instalar as Dependências

Com o ambiente ativado, instale as bibliotecas Python necessárias (FastAPI, Uvicorn, etc.):

```bash
pip install -r requirements.txt
```

-----

## ▶️ Como Rodar a Aplicação

O EcoGrid é um servidor web. Use o `uvicorn` para iniciá-lo.

### 1\. Iniciar o Servidor

Execute o servidor Uvicorn a partir do diretório raiz:

```bash
uvicorn app:app --reload --port 8000
```

### 2\. Acessar a Interface

Abra seu navegador e acesse o endereço:

**`http://127.0.0.1:8000`** ou **`http://localhost:8000`**

Você poderá interagir com o menu principal para carregar a rede, simular eventos e modificar os nós, visualizando as mudanças em tempo real na árvore D3.js.

-----

## 📸 Demonstração

**(Espaço para as Capturas de Tela - Adicionar depois)**

### Visualização da Rede Inicial:

*Captura de tela mostrando a árvore da rede elétrica inicial (Subestações, Transformadores e Consumidores) em estado "Normal".*

### Simulação de Sobrecarga e Logs:

*Exemplo de uma simulação em andamento, onde o nó afetado muda para o status **Overloaded** (vermelho) e as mensagens de logs são exibidas.*