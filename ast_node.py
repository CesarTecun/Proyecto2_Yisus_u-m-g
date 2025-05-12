class ASTNode:
    def __init__(self, type, value=None, children=None):
        self.type = type
        self.value = value
        self.children = children or []

    def __repr__(self):
        children_repr = f"[{', '.join(repr(child) for child in self.children)}]" if self.children else "[]"
        return f"ASTNode(type={self.type}, value={repr(self.value)}, children={children_repr})"
