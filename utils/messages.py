from settings import MESSAGES, MESSAGES_STATIC


def _resolve(source, path: str):
    node = source
    for key in path.split('.'):
        if not isinstance(node, dict):
            return None
        node = node.get(key)
        if node is None:
            return None
    return node


def get_message(path: str, **kwargs) -> str:
    node = _resolve(MESSAGES, path)
    if node is None:
        node = _resolve(MESSAGES_STATIC, path)
    if node is None:
        return f"[missing message: {path}]"
    if isinstance(node, str):
        return node.format(**kwargs)
    return node