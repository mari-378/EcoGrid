from __future__ import annotations

import argparse
import json
from pathlib import Path

from api.backend_facade import PowerGridBackend


def parse_args() -> argparse.Namespace:
    """
    Analisa argumentos de linha de comando para executar cenários de
    teste da camada lógica via Facade.
    """
    parser = argparse.ArgumentParser(
        description="Sandbox para testar a camada lógica da rede (Backend Facade).",
    )

    parser.add_argument(
        "--nodes-path",
        type=str,
        default="out/nodes",
        help='Caminho para o arquivo de nós (padrão: "out/nodes").',
    )

    parser.add_argument(
        "--edges-path",
        type=str,
        default="out/edges",
        help='Caminho para o arquivo de arestas (padrão: "out/edges").',
    )

    parser.add_argument(
        "--mode",
        type=str,
        default="snapshot",
        choices=["snapshot", "remove-node"],
        help=(
            "Cenário de teste a executar. "
            '"snapshot" gera apenas a árvore de UI. '
            '"remove-node" remove um nó lógico e gera a árvore resultante.'
        ),
    )

    parser.add_argument(
        "--node-id",
        type=str,
        default=None,
        help=(
            "Identificador do nó a ser usado em cenários que exigem nó "
            'específico (por exemplo, "--mode remove-node").'
        ),
    )

    parser.add_argument(
        "--out",
        type=str,
        default="out.txt",
        help='Caminho do arquivo de saída do snapshot (padrão: "out.txt").',
    )

    return parser.parse_args()


def _write_output(data: dict, out_path: str) -> None:
    """Helper para escrever JSON de saída."""
    path = Path(out_path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main() -> None:
    """
    Função principal refatorada para usar o PowerGridBackend (Facade).
    """
    args = parse_args()

    # 1. Inicialização Simplificada via Facade
    backend = PowerGridBackend(
        nodes_path=args.nodes_path,
        edges_path=args.edges_path,
    )

    # 2. Execução de Cenários
    result = {}

    if args.mode == "snapshot":
        result = backend.get_tree_snapshot()

    elif args.mode == "remove-node":
        if not args.node_id:
            raise SystemExit(
                "Erro: --node-id é obrigatório quando --mode=remove-node",
            )
        result = backend.remove_node(node_id=args.node_id)

    # 3. Escrita do Resultado
    _write_output(result, args.out)


if __name__ == "__main__":
    main()
