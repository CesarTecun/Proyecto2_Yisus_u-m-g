from LenVisitor import LenVisitor
from LenParser import LenParser

class ASTNode:
    def __init__(self, type, value=None, children=None):
        self.type = type
        self.value = value
        self.children = children or []

    def __repr__(self):
        children_repr = f"[{', '.join(repr(child) for child in self.children)}]" if self.children else "[]"
        return f"ASTNode(type={self.type}, value={repr(self.value)}, children={children_repr})"



class ASTBuilder(LenVisitor):
    def visitProg(self, ctx):
        children = []
        for decl in ctx.declaracion_global():
            children.append(self.visit(decl))
        if ctx.funciones():
            children.append(self.visit(ctx.funciones()))
        children.append(self.visit(ctx.bloque_PROGRAM()))
        return ASTNode("Program", children=children)

    def visitDeclaracionGlobalSimple(self, ctx):
        tipo = ctx.tipo().getText().lower()
        nombre = ctx.ID().getText()
        expr = self.visit(ctx.expr()) if ctx.expr() else None
        return ASTNode("GlobalDeclaration", value={'tipo': tipo, 'nombre': nombre}, children=[expr] if expr else [])

    def visitDeclaracionSimple(self, ctx):
        tipo = ctx.tipo().getText().lower()
        nombre = ctx.ID().getText()
        expr = self.visit(ctx.expr()) if ctx.expr() else None
        return ASTNode("Declaration", value={'tipo': tipo, 'nombre': nombre}, children=[expr] if expr else [])

    def visitDeclaracionInferida(self, ctx):
        nombre = ctx.ID().getText()
        expr = self.visit(ctx.expr())
        return ASTNode("InferredDeclaration", value=nombre, children=[expr])

    def visitDeclaracionSentencia(self, ctx):
        return self.visit(ctx.declaracion())

    def visitFunciones(self, ctx):
        return ASTNode("Functions", children=[self.visit(f) for f in ctx.funcion()])

    def visitFuncionDef(self, ctx):
        tipo_ret = ctx.tipo().getText().lower() if ctx.tipo() else "void"
        nombre = ctx.ID().getText()
        parametros = []
        if ctx.params() and hasattr(ctx.params(), "param"):
            for p in ctx.params().param():
                tipo = p.tipo().getText().lower()
                iden = p.ID().getText()
                parametros.append(ASTNode("Param", value={'tipo': tipo, 'nombre': iden}))
        cuerpo = self.visit(ctx.bloque())
        return ASTNode("Function", value={'nombre': nombre, 'tipo': tipo_ret}, children=parametros + [cuerpo])

    def visitBloque_PROGRAM(self, ctx):
        return self.visit(ctx.bloque())

    def visitBloque(self, ctx):
        sentencias = []
        for s in ctx.sentencia():
            nodo = self.visit(s)
            if nodo is not None:
                sentencias.append(nodo)
        return ASTNode("Block", children=sentencias)

    def visitSentencia(self, ctx):
        if ctx.asignacionExp():
            return self.visit(ctx.asignacionExp())
        elif ctx.MOSTRARSentencia():
            return self.visit(ctx.MOSTRARSentencia())
        elif ctx.siSentencia():
            return self.visit(ctx.siSentencia())
        elif ctx.LOPSentencia():
            return self.visit(ctx.LOPSentencia())
        elif ctx.hacerLOPSentencia():
            return self.visit(ctx.hacerLOPSentencia())
        elif ctx.paraSentencia():
            return self.visit(ctx.paraSentencia())
        elif ctx.retornarSentencia():
            return self.visit(ctx.retornarSentencia())
        elif ctx.bloque():
            return self.visit(ctx.bloque())
        elif ctx.declaracion():
            return self.visit(ctx.declaracion())
        else:
            return None

    def visitMOSTRARSentencia(self, ctx):
        args = [self.visit(e) for e in ctx.args().expr()] if ctx.args() else []
        return ASTNode("Print", children=args)

    def visitSiSentencia(self, ctx):
        cond = self.visit(ctx.expr())
        entonces = self.visit(ctx.sentencia(0))
        sino = self.visit(ctx.sentencia(1)) if ctx.SINO() else None
        children = [cond, entonces] + ([sino] if sino else [])
        return ASTNode("If", children=children)

    def visitLOPSentencia(self, ctx):
        cond = self.visit(ctx.expr())
        cuerpo = self.visit(ctx.sentencia())
        return ASTNode("While", children=[cond, cuerpo])

    def visitHacerLOPSentencia(self, ctx):
        cuerpo = self.visit(ctx.sentencia())
        cond = self.visit(ctx.expr())
        return ASTNode("DoWhile", children=[cuerpo, cond])

    def visitParaSentencia(self, ctx):
        init = self.visit(ctx.declaracion()) if ctx.declaracion() else self.visit(ctx.expr(0))
        cond = self.visit(ctx.expr(1)) if ctx.expr(1) else None
        step = self.visit(ctx.expr(2)) if ctx.expr(2) else None
        cuerpo = self.visit(ctx.sentencia())
        return ASTNode("For", children=[init, cond, step, cuerpo])

    def visitRetornarSentencia(self, ctx):
        expr = self.visit(ctx.expr()) if ctx.expr() else None
        return ASTNode("Return", children=[expr] if expr else [])

    def visitAsignacionSentencia(self, ctx):
        return self.visit(ctx.asignacion())

    def visitAsignacion(self, ctx):
        if ctx.getChildCount() == 3:
            nombre = ctx.ID().getText()
            valor = self.visit(ctx.asignacion())
            return ASTNode("Assign", value=nombre, children=[valor])
        else:
            return self.visit(ctx.logicaOr())

    def visitAsignacionExp(self, ctx):
        nombre = ctx.ID().getText()
        valor = self.visit(ctx.asignacion())
        return ASTNode("Assign", value=nombre, children=[valor])

    def visitSoloExp(self, ctx): return self.visit(ctx.logicaOr())
    def visitOpLogicaOR(self, ctx):
        return ASTNode("BinaryOp", value="or", children=[self.visit(ctx.logicaOr()), self.visit(ctx.logicaAnd())])
    def visitSoloLogicaAnd(self, ctx): return self.visit(ctx.logicaAnd())
    def visitOpLogicaAND(self, ctx):
        return ASTNode("BinaryOp", value="and", children=[self.visit(ctx.logicaAnd()), self.visit(ctx.igualdad())])
    def visitSoloIgualdad(self, ctx): return self.visit(ctx.igualdad())
    def visitOpIgualdadDiferencia(self, ctx):
        op = ctx.getChild(1).getText()
        return ASTNode("BinaryOp", value=op, children=[self.visit(ctx.igualdad()), self.visit(ctx.comparacion())])
    def visitSoloComparacion(self, ctx): return self.visit(ctx.comparacion())
    def visitOpComparacion(self, ctx):
        op = ctx.getChild(1).getText()
        return ASTNode("BinaryOp", value=op, children=[self.visit(ctx.comparacion()), self.visit(ctx.suma())])
    def visitSoloSuma(self, ctx): return self.visit(ctx.suma())
    def visitOpSumaResta(self, ctx):
        op = ctx.getChild(1).getText()
        return ASTNode("BinaryOp", value=op, children=[self.visit(ctx.suma()), self.visit(ctx.mult())])
    def visitSoloMult(self, ctx): return self.visit(ctx.mult())
    def visitOpMultDiv(self, ctx):
        op = ctx.getChild(1).getText()
        return ASTNode("BinaryOp", value=op, children=[self.visit(ctx.mult()), self.visit(ctx.potencia())])
    def visitSoloPotencia(self, ctx): return self.visit(ctx.potencia())
    def visitOpPotencia(self, ctx):
        return ASTNode("BinaryOp", value="^", children=[self.visit(ctx.unario()), self.visit(ctx.potencia())])
    def visitSoloUnario(self, ctx): return self.visit(ctx.unario())
    def visitOpUnarioNot(self, ctx):
        return ASTNode("UnaryOp", value="not", children=[self.visit(ctx.unario())])
    def visitOpUnarioPositivo(self, ctx):
        return ASTNode("UnaryOp", value="+", children=[self.visit(ctx.unario())])
    def visitOpUnarioNegativo(self, ctx):
        return ASTNode("UnaryOp", value="-", children=[self.visit(ctx.unario())])
    def visitLlamadaUnaria(self, ctx): return self.visit(ctx.llamada())
    def visitParentesis(self, ctx): return self.visit(ctx.expr())
    def visitNumero(self, ctx):
        txt = ctx.getText()
        val = float(txt) if '.' in txt else int(txt)
        return ASTNode("Literal", value=val)
    def visitBooleano(self, ctx):
        return ASTNode("Literal", value=ctx.BOOL_LIT().getText().lower() == 'true')
    def visitTexto(self, ctx):
        return ASTNode("Literal", value=ctx.TEXTO().getText()[1:-1])
    def visitVariable(self, ctx):
        return ASTNode("Variable", value=ctx.ID().getText())
    def visitArgumentos(self, ctx):
        return [self.visit(e) for e in ctx.expr()]
    def visitLlamadaFuncion(self, ctx):
        if ctx.getChildCount() == 1:
            return self.visit(ctx.primary())
        nombre = ctx.primary().ID().getText()
        args = self.visit(ctx.args(0)) if ctx.args() else []
        return ASTNode("FunctionCall", value=nombre, children=args)