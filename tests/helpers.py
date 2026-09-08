"""Deep-mutation helpers for building invalid document variants in tests."""

import copy


def set_path(document: dict, dotted_path: str, value) -> dict:
    """Return a deep copy of *document* with a nested field set to *value*."""
    doc = copy.deepcopy(document)
    node = doc
    keys = dotted_path.split(".")
    for key in keys[:-1]:
        node = node[key]
    node[keys[-1]] = value
    return doc


def del_path(document: dict, dotted_path: str) -> dict:
    """Return a deep copy of *document* with a nested field removed."""
    doc = copy.deepcopy(document)
    node = doc
    keys = dotted_path.split(".")
    for key in keys[:-1]:
        node = node[key]
    del node[keys[-1]]
    return doc
