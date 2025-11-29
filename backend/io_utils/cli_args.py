from __future__ import annotations

import argparse
from typing import List, Optional

from config import SimulationConfig


def build_arg_parser() -> argparse.ArgumentParser:
    """
    Cria e configura o parser de argumentos de linha de comando.

    Esta função define todos os parâmetros de CLI que podem influenciar
    a simulação, mapeando-os diretamente para os campos de
    `SimulationConfig`. A ideia é permitir:

        - ajustar rapidamente o tamanho da região;
        - controlar quantidades de nós (usinas, TS, DS, consumidores);
        - alterar parâmetros principais de transmissão, MV, LV e robustez
          sem precisar editar código.

    O parser não executa a simulação; ele apenas interpreta os argumentos
    e entrega um objeto pronto para ser usado ao construir a configuração.

    Retorna:
        Uma instância de `argparse.ArgumentParser` pronta para uso, que
        pode ser utilizada com `parse_args()` para obter os argumentos
        fornecidos pelo usuário.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Gerador de rede elétrica sintética em múltiplas camadas "
            "(transmissão, média e baixa tensão) com heurísticas de "
            "robustez aproximando N–k."
        )
    )

    # ------------------------------------------------------------------
    # Grupo: dimensões da região
    # ------------------------------------------------------------------
    region_group = parser.add_argument_group("Região de simulação")
    region_group.add_argument(
        "--region-width",
        type=float,
        default=None,
        help="Largura da área de simulação (eixo X).",
    )
    region_group.add_argument(
        "--region-height",
        type=float,
        default=None,
        help="Altura da área de simulação (eixo Y).",
    )

    # ------------------------------------------------------------------
    # Grupo: clusters e quantidades de nós
    # ------------------------------------------------------------------
    cluster_group = parser.add_argument_group("Clusters e quantidades de nós")
    cluster_group.add_argument(
        "--num-load-clusters",
        type=int,
        default=None,
        help="Número de clusters de carga (bairros / zonas).",
    )
    cluster_group.add_argument(
        "--num-generation-plants",
        type=int,
        default=None,
        help="Número de usinas de geração.",
    )
    cluster_group.add_argument(
        "--num-transmission-substations",
        type=int,
        default=None,
        help="Número de subestações de transmissão (TS).",
    )
    cluster_group.add_argument(
        "--num-distribution-substations",
        type=int,
        default=None,
        help="Número de subestações de distribuição (DS).",
    )
    cluster_group.add_argument(
        "--num-consumers",
        type=int,
        default=None,
        help="Número de pontos consumidores agregados.",
    )

    # ------------------------------------------------------------------
    # Grupo: transmissão
    # ------------------------------------------------------------------
    tx_group = parser.add_argument_group("Transmissão (alta tensão)")
    tx_group.add_argument(
        "--tx-max-segment-length",
        type=float,
        default=None,
        help="Comprimento máximo típico de segmento em alta tensão.",
    )
    tx_group.add_argument(
        "--tx-ts-k-neighbors",
        type=int,
        default=None,
        help=(
            "Número de vizinhos mais próximos considerados entre TS "
            "na construção do backbone."
        ),
    )
    tx_group.add_argument(
        "--tx-generation-k-neighbors",
        type=int,
        default=None,
        help=(
            "Número de subestações de transmissão vizinhas consideradas "
            "para cada usina de geração."
        ),
    )
    tx_group.add_argument(
        "--tx-target-avg-degree-ts",
        type=float,
        default=None,
        help="Grau médio alvo das subestações de transmissão.",
    )
    tx_group.add_argument(
        "--tx-max-degree-ts",
        type=int,
        default=None,
        help="Grau máximo permitido por TS em alta tensão.",
    )

    # ------------------------------------------------------------------
    # Grupo: média tensão
    # ------------------------------------------------------------------
    mv_group = parser.add_argument_group("Média tensão (TS↔DS, DS↔DS)")
    mv_group.add_argument(
        "--mv-max-segment-length",
        type=float,
        default=None,
        help="Comprimento máximo típico de segmento em média tensão.",
    )
    mv_group.add_argument(
        "--mv-ds-k-neighbors-ts",
        type=int,
        default=None,
        help="Número de TS vizinhas consideradas ao conectar DS em MV.",
    )
    mv_group.add_argument(
        "--mv-min-ts-per-ds",
        type=int,
        default=None,
        help="Número mínimo desejado de TS ligadas a cada DS em MV.",
    )
    mv_group.add_argument(
        "--mv-max-ds-per-ts-primary",
        type=int,
        default=None,
        help="Limite aproximado de DS primárias por TS em MV.",
    )
    mv_group.add_argument(
        "--mv-max-ds-per-ts-total",
        type=int,
        default=None,
        help="Limite aproximado de DS totais (primárias+redundantes) por TS.",
    )
    mv_group.add_argument(
        "--mv-ds-k-neighbors-ds",
        type=int,
        default=None,
        help="Número de vizinhos DS considerados na malha DS↔DS.",
    )
    mv_group.add_argument(
        "--mv-target-avg-degree-ds",
        type=float,
        default=None,
        help="Grau médio alvo para DS em média tensão.",
    )
    mv_group.add_argument(
        "--mv-max-degree-ds",
        type=int,
        default=None,
        help="Grau máximo permitido por DS em MV.",
    )
    mv_group.add_argument(
        "--mv-intercluster-links-per-pair",
        type=int,
        default=None,
        help=(
            "Número máximo de ligações DS↔DS em MV para cada par de clusters."
        ),
    )

    # ------------------------------------------------------------------
    # Grupo: baixa tensão
    # ------------------------------------------------------------------
    lv_group = parser.add_argument_group("Baixa tensão (DS↔consumidores)")
    lv_group.add_argument(
        "--lv-max-segment-length",
        type=float,
        default=None,
        help="Comprimento máximo típico de ramal em baixa tensão.",
    )
    lv_group.add_argument(
        "--lv-ds-k-neighbors",
        type=int,
        default=None,
        help="Número de DS vizinhas consideradas para cada consumidor.",
    )
    lv_group.add_argument(
        "--lv-min-ds-per-consumer",
        type=int,
        default=None,
        help="Número mínimo desejado de DS por consumidor.",
    )
    lv_group.add_argument(
        "--lv-max-consumers-per-ds-primary",
        type=int,
        default=None,
        help="Limite aproximado de consumidores primários por DS.",
    )
    lv_group.add_argument(
        "--lv-max-consumers-per-ds-total",
        type=int,
        default=None,
        help="Limite aproximado de consumidores totais por DS.",
    )
    lv_group.add_argument(
        "--consumer-base-demand",
        type=float,
        default=None,
        help="Demanda base típica de cada consumidor.",
    )
    lv_group.add_argument(
        "--consumer-demand-variation",
        type=float,
        default=None,
        help=(
            "Variação percentual da demanda dos consumidores (ex.: 0.5 "
            "para 50% a 150% do valor base)."
        ),
    )

    # ------------------------------------------------------------------
    # Grupo: robustez
    # ------------------------------------------------------------------
    robust_group = parser.add_argument_group("Robustez (heurística N–k)")
    robust_group.add_argument(
        "--robust-max-extra-edges-total",
        type=int,
        default=None,
        help="Número máximo de arestas extras que a etapa de robustez pode criar.",
    )
    robust_group.add_argument(
        "--robust-max-extra-edges-ts",
        type=int,
        default=None,
        help="Número máximo de arestas extras TS↔TS em alta tensão.",
    )
    robust_group.add_argument(
        "--robust-max-extra-edges-ds",
        type=int,
        default=None,
        help="Número máximo de arestas extras DS↔TS em média tensão.",
    )
    robust_group.add_argument(
        "--robust-articulation-impact-threshold",
        type=int,
        default=None,
        help="Impacto mínimo para considerar um nó como articulação crítica.",
    )
    robust_group.add_argument(
        "--robust-ts-k-reinforcement",
        type=int,
        default=None,
        help="Número de vizinhos TS considerados no reforço de transmissão.",
    )
    robust_group.add_argument(
        "--robust-reinforcement-length-factor",
        type=float,
        default=None,
        help=(
            "Fator multiplicador para comprimentos de reforço em "
            "transmissão e média tensão."
        ),
    )
    robust_group.add_argument(
        "--robust-max-degree-ts",
        type=int,
        default=None,
        help="Grau máximo permitido para TS na etapa de robustez.",
    )
    robust_group.add_argument(
        "--robust-max-degree-ds-mv",
        type=int,
        default=None,
        help="Grau máximo permitido para DS em MV na etapa de robustez.",
    )
    robust_group.add_argument(
        "--robust-min-ts-diversity-per-ds",
        type=int,
        default=None,
        help=(
            "Número mínimo desejado de TS ascendentes para cada DS após "
            "o reforço de robustez."
        ),
    )

    return parser


def config_from_args(args: Optional[List[str]] = None) -> SimulationConfig:
    """
    Constrói um `SimulationConfig` a partir da linha de comando.

    Esta função:

        1) Cria um parser de argumentos com `build_arg_parser()`;
        2) Interpreta `args` (ou `sys.argv` se `args` for `None`);
        3) Cria uma instância de `SimulationConfig` com valores padrão;
        4) Para cada argumento presente, sobrescreve o campo correspondente
           em `SimulationConfig`.

    A lógica de mapeamento entre nomes de argumentos e campos usa
    convenções simples:

        - `--region-width` → `region_width`
        - `--num-generation-plants` → `num_generation_plants`
        - `--tx-max-segment-length` → `transmission_max_segment_length`
        - etc.

    Os valores que permanecem `None` em `argparse` indicam que o campo
    não foi sobrescrito, mantendo o padrão definido em `SimulationConfig`.

    Args:
        args:
            Lista opcional de strings com os argumentos de linha de
            comando. Se `None`, os argumentos reais de `sys.argv` serão
            utilizados.

    Returns:
        Uma instância de `SimulationConfig` com todos os campos
        ajustados de acordo com os argumentos fornecidos.
    """
    parser = build_arg_parser()
    parsed = parser.parse_args(args=args)

    cfg = SimulationConfig()

    # Helper para sobrescrever campo se argumento não for None
    def override(field: str, value) -> None:
        if value is not None:
            setattr(cfg, field, value)

    # Região
    override("region_width", parsed.region_width)
    override("region_height", parsed.region_height)

    # Clusters / nós
    override("num_load_clusters", parsed.num_load_clusters)
    override("num_generation_plants", parsed.num_generation_plants)
    override(
        "num_transmission_substations",
        parsed.num_transmission_substations,
    )
    override(
        "num_distribution_substations",
        parsed.num_distribution_substations,
    )
    override("num_consumers", parsed.num_consumers)

    # Transmissão
    override(
        "transmission_max_segment_length",
        parsed.tx_max_segment_length,
    )
    override(
        "transmission_ts_k_neighbors",
        parsed.tx_ts_k_neighbors,
    )
    override(
        "transmission_generation_k_neighbors",
        parsed.tx_generation_k_neighbors,
    )
    override(
        "transmission_target_avg_degree_ts",
        parsed.tx_target_avg_degree_ts,
    )
    override(
        "transmission_max_degree_ts",
        parsed.tx_max_degree_ts,
    )

    # Média tensão
    override("mv_max_segment_length", parsed.mv_max_segment_length)
    override("mv_ds_k_neighbors_ts", parsed.mv_ds_k_neighbors_ts)
    override("mv_min_ts_per_ds", parsed.mv_min_ts_per_ds)
    override(
        "mv_max_ds_per_ts_primary",
        parsed.mv_max_ds_per_ts_primary,
    )
    override("mv_max_ds_per_ts_total", parsed.mv_max_ds_per_ts_total)
    override("mv_ds_k_neighbors_ds", parsed.mv_ds_k_neighbors_ds)
    override("mv_target_avg_degree_ds", parsed.mv_target_avg_degree_ds)
    override("mv_max_degree_ds", parsed.mv_max_degree_ds)
    override(
        "mv_intercluster_links_per_pair",
        parsed.mv_intercluster_links_per_pair,
    )

    # Baixa tensão
    override("lv_max_segment_length", parsed.lv_max_segment_length)
    override("lv_ds_k_neighbors", parsed.lv_ds_k_neighbors)
    override("lv_min_ds_per_consumer", parsed.lv_min_ds_per_consumer)
    override(
        "lv_max_consumers_per_ds_primary",
        parsed.lv_max_consumers_per_ds_primary,
    )
    override(
        "lv_max_consumers_per_ds_total",
        parsed.lv_max_consumers_per_ds_total,
    )
    override("consumer_base_demand", parsed.consumer_base_demand)
    override(
        "consumer_demand_variation",
        parsed.consumer_demand_variation,
    )

    # Robustez
    override(
        "robust_max_extra_edges_total",
        parsed.robust_max_extra_edges_total,
    )
    override(
        "robust_max_extra_edges_ts",
        parsed.robust_max_extra_edges_ts,
    )
    override(
        "robust_max_extra_edges_ds",
        parsed.robust_max_extra_edges_ds,
    )
    override(
        "robust_articulation_impact_threshold",
        parsed.robust_articulation_impact_threshold,
    )
    override(
        "robust_ts_k_reinforcement",
        parsed.robust_ts_k_reinforcement,
    )
    override(
        "robust_reinforcement_length_factor",
        parsed.robust_reinforcement_length_factor,
    )
    override("robust_max_degree_ts", parsed.robust_max_degree_ts)
    override("robust_max_degree_ds_mv", parsed.robust_max_degree_ds_mv)
    override(
        "robust_min_ts_diversity_per_ds",
        parsed.robust_min_ts_diversity_per_ds,
    )

    return cfg


__all__ = ["build_arg_parser", "config_from_args"]
