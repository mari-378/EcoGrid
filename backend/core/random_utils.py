from __future__ import annotations

import math
import random
from typing import List, Optional, Sequence, Tuple


def sample_point_in_circle(
    center_x: float,
    center_y: float,
    radius: float,
    rng: Optional[random.Random] = None,
) -> Tuple[float, float]:
    """
    Gera um ponto aleatório dentro de um círculo 2D.

    O ponto é amostrado de forma aproximadamente uniforme na área do
    círculo, usando coordenadas polares com raio ajustado por raiz
    quadrada (r = R * sqrt(u)). Esta função é útil para distribuir nós
    em torno de um centro de cluster ou de uma subestação, mantendo uma
    densidade homogênea na região.

    Args:
        center_x:
            Coordenada X do centro do círculo.
        center_y:
            Coordenada Y do centro do círculo.
        radius:
            Raio máximo do círculo, na mesma unidade das coordenadas
            cartesianas da simulação.
        rng:
            Instância opcional de `random.Random` a ser usada como fonte
            de aleatoriedade. Se `None`, será utilizado o gerador global
            do módulo `random`.

    Returns:
        Uma tupla `(x, y)` representando as coordenadas cartesianas do
        ponto gerado dentro do círculo.
    """
    if rng is None:
        rng = random

    u = rng.random()
    r = radius * math.sqrt(u)
    theta = 2.0 * math.pi * rng.random()

    x = center_x + r * math.cos(theta)
    y = center_y + r * math.sin(theta)
    return x, y


def poisson_disk_sampling(
    width: float,
    height: float,
    radius: float,
    k: int = 30,
    rng: Optional[random.Random] = None,
) -> List[Tuple[float, float]]:
    """
    Gera pontos 2D usando amostragem de Poisson em disco (método de Bridson).

    Esta função cria um conjunto de pontos aproximadamente uniformemente
    distribuídos sobre um retângulo `[0, width] x [0, height]`, garantindo
    que a distância mínima entre quaisquer dois pontos seja, em média,
    próxima ao raio especificado. O algoritmo é baseado no método de
    Bridson para amostragem de Poisson em disco.

    Uso típico no contexto do projeto:
        - Geração de centros de clusters de carga suficientemente
          espaçados.
        - Distribuição de subestações dentro de uma região sem pontos
          excessivamente próximos entre si.

    Parâmetros principais:
        - `radius` controla a distância mínima entre pontos. Quanto maior
          o raio, mais espaçados e menos numerosos serão os pontos.
        - `k` controla o número máximo de tentativas de geração de novos
          pontos ao redor de cada ponto ativo. Valores em torno de 20–30
          costumam ser um bom compromisso entre qualidade e desempenho.

    Args:
        width:
            Largura do retângulo de amostragem (extensão no eixo X).
        height:
            Altura do retângulo de amostragem (extensão no eixo Y).
        radius:
            Raio mínimo aproximado entre pontos. O algoritmo tenta
            garantir que nenhuma dupla de pontos fique mais próxima do
            que este valor.
        k:
            Número máximo de tentativas de geração de novos pontos em
            torno de cada ponto ativo antes que ele seja considerado
            "esgotado". Valores mais altos aumentam a qualidade da
            amostragem, mas também o custo computacional.
        rng:
            Instância opcional de `random.Random` a ser usada como fonte
            de aleatoriedade. Se `None`, será utilizado o gerador global
            do módulo `random`.

    Returns:
        Uma lista de tuplas `(x, y)` com as coordenadas dos pontos
        gerados dentro do retângulo especificado.

    Observações importantes:
        - A implementação é totalmente determinística para um dado estado
          do gerador aleatório. Para reprodutibilidade, recomenda-se
          fornecer um `random.Random` com semente fixa.
        - O algoritmo tem custo aproximado linear no número de pontos
          gerados para tamanhos de problema típicos, sendo adequado para
          gerar centenas ou milhares de pontos em aplicações de
          planejamento.
    """
    if rng is None:
        rng = random

    if radius <= 0.0:
        raise ValueError("radius deve ser maior que zero.")

    # Tamanho da célula da grade auxiliar. A escolha radius / sqrt(2)
    # garante que basta verificar vizinhos em um pequeno entorno na
    # grade para respeitar a distância mínima.
    cell_size = radius / math.sqrt(2.0)

    grid_width = int(math.ceil(width / cell_size))
    grid_height = int(math.ceil(height / cell_size))

    # Grade de índices de pontos: cada célula guarda o índice do ponto
    # na lista `samples` ou None se vazia.
    grid: List[List[Optional[int]]] = [
        [None for _ in range(grid_height)] for _ in range(grid_width)
    ]

    samples: List[Tuple[float, float]] = []
    active_list: List[Tuple[float, float]] = []

    # Gera o primeiro ponto aleatório dentro da área.
    first_x = rng.uniform(0.0, width)
    first_y = rng.uniform(0.0, height)
    samples.append((first_x, first_y))
    active_list.append((first_x, first_y))

    gx = int(first_x / cell_size)
    gy = int(first_y / cell_size)
    grid[gx][gy] = 0

    # Função auxiliar para verificar se uma coordenada está dentro da área.
    def _in_bounds(px: float, py: float) -> bool:
        return 0.0 <= px < width and 0.0 <= py < height

    while active_list:
        # Escolhe aleatoriamente um ponto ativo para gerar novos candidatos.
        idx = rng.randrange(len(active_list))
        base_x, base_y = active_list[idx]

        found_new_point = False
        for _ in range(k):
            # Gera um novo ponto em um anel entre radius e 2 * radius
            angle = rng.uniform(0.0, 2.0 * math.pi)
            rad = radius * (1.0 + rng.random())
            px = base_x + rad * math.cos(angle)
            py = base_y + rad * math.sin(angle)

            if not _in_bounds(px, py):
                continue

            # Determina a célula da grade correspondente ao novo ponto.
            cell_x = int(px / cell_size)
            cell_y = int(py / cell_size)

            # Verifica os vizinhos próximos na grade para garantir que
            # nenhum ponto existente esteja mais perto que `radius`.
            ok = True
            # Verificamos um pequeno entorno em torno da célula alvo.
            for ix in range(max(cell_x - 2, 0), min(cell_x + 3, grid_width)):
                for iy in range(
                    max(cell_y - 2, 0),
                    min(cell_y + 3, grid_height),
                ):
                    sidx = grid[ix][iy]
                    if sidx is None:
                        continue
                    sx, sy = samples[sidx]
                    if math.hypot(sx - px, sy - py) < radius:
                        ok = False
                        break
                if not ok:
                    break

            if not ok:
                continue

            # Ponto aceito: registramos nas estruturas.
            samples.append((px, py))
            active_list.append((px, py))
            grid[cell_x][cell_y] = len(samples) - 1
            found_new_point = True
            break

        # Se não foi possível gerar novos pontos em torno deste ativo,
        # ele é removido da lista.
        if not found_new_point:
            active_list.pop(idx)

    return samples


__all__: Sequence[str] = [
    "sample_point_in_circle",
    "poisson_disk_sampling",
]
