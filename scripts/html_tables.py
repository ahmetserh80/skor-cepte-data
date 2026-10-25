from html import escape

def serialize(node):
    if isinstance(node,str): return escape(node)
    attrs=''.join(f' {k}="{escape(v or "",quote=True)}"' for k,v in node.attrs.items())
    if node.tag in ('br','img','input','hr','meta','link'): return f'<{node.tag}{attrs}>'
    return f'<{node.tag}{attrs}>'+''.join(serialize(n) for n in node.children)+f'</{node.tag}>'
