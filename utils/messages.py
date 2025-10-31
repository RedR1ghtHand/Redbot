from settings import MESSAGES


def get_message(path: str, **kwargs) -> str:
    node = MESSAGES
    for key in path.split('.'):
        node = node.get(key)
        if node is None:
            return f"[missing message: {path}]"
    if isinstance(node, str):
        return node.format(**kwargs)
    return node