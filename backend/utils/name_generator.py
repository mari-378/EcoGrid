import hashlib

_BRAZILIAN_NAMES = [
    "Abacate", "Bicicleta", "Curitiba", "Samba", "Capivara",
    "Futebol", "Caipirinha", "Pão de Queijo", "Brigadeiro", "Amazonas",
    "Recife", "Salvador", "Pantanal", "Cachoeira", "Ipê",
    "Jabuticaba", "Tatu", "Arara", "Tucano", "Feijoada",
    "Carnaval", "Tapioca", "Chimarrão", "Acarajé", "Bauru",
    "Coxinha", "Guaraná", "Mandacaru", "Saci", "Iara",
    "Boto", "Mico", "Tamanduá", "Onça", "Piranha",
    "Jaguatirica", "Sucuri", "Tuiuiú", "Vitória-Régia", "Cerrado",
    "Caatinga", "Pampa", "Araucária", "Jequitibá", "Peroba",
    "Jacarandá", "Mogno", "Imbuia", "Carnaúba", "Babaçu"
]

def get_name_for_cluster(cluster_id: int) -> str:
    """
    Returns a deterministic name for a given cluster ID.
    """
    if cluster_id is None:
        return "N/A"

    # Use a simple deterministic mapping.
    # We can just use modulo, but to make it feel more "random" but deterministic,
    # we can use a hash or a pseudo-random generator seeded with the ID.
    # However, simple modulo might be enough if the IDs are sequential.
    # If IDs are 0, 1, 2... simple modulo is fine.

    # Let's use a slightly more "mixed" index to avoid adjacent words always being adjacent
    # just in case the list is sorted alphabetically or by category.
    # (The list above seems somewhat random/categorized).

    # Using a hash ensures that ID 0 and ID 1 might pick words far apart in the list.

    hash_object = hashlib.md5(str(cluster_id).encode())
    hash_int = int(hash_object.hexdigest(), 16)

    index = hash_int % len(_BRAZILIAN_NAMES)
    return _BRAZILIAN_NAMES[index]
