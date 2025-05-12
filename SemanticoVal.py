from antlr4 import *
from LenParser import LenParser
from LenListener import LenListener
from collections import deque

class SemanticError(Exception):
    pass

class Scope:
    def __init__(self):
        self.variables = {}
        self.functions = {}

class SemanticListener(LenListener):
    def __init__(self):
        self.scopes = deque([Scope()])
        self.current_function_return_type = None
        self.called_functions = set()
        self.errors = []
        self.warnings = []

    def _map_type(self, raw_type):
        t = raw_type.lower()
        if t in ["int", "entero"]: return "entero"
        if t in ["flt", "decimal"]: return "decimal"
        if t in ["str", "cadena"]: return "cadena"
        if t in ["bool", "bol"]: return "bool"
        if t in ["void", "vd"]: return "void"
        return t

    def _is_compatible_assignment(self, declared, actual):
        if declared == actual:
            return True
        if declared == "decimal" and actual == "entero":
            return True
        return False

    def enterBloque(self, ctx: LenParser.BloqueContext):
        self.scopes.append(Scope())

    def exitBloque(self, ctx: LenParser.BloqueContext):
        scope = self.scopes.pop()
        for name, meta in scope.variables.items():
            if not meta.get("read", False) and not meta.get("assigned", False):
                self._warn(meta.get("ctx", ctx), f"La variable '{name}' fue declarada pero nunca utilizada en este bloque.")
            elif meta.get("assigned", False) and not meta.get("read", False):
                self._warn(meta.get("ctx", ctx), f"La variable '{name}' fue asignada pero nunca leída en este bloque.")
        if len(self.scopes) == 0:
            for scope in self.scopes:
                for name in scope.functions:
                    if name not in self.called_functions:
                        self._warn(ctx, f"La función '{name}' fue definida pero nunca llamada.")

    def enterLOPSentencia(self, ctx: LenParser.LOPSentenciaContext):
        try:
            expr_ctx = ctx.expr()
            if isinstance(expr_ctx, list):
                expr_ctx = expr_ctx[0]
            inferred = self._infer_expr_type(expr_ctx)
            cond_type = self._map_type(inferred)
        except Exception:
            cond_type = "entero"

        if cond_type != "bool":
            self._error(ctx.expr(), f"La condición en un 'loop' debe ser de tipo 'bool'. Actualmente es '{cond_type}'.")

    def enterParaSentencia(self, ctx: LenParser.ParaSentenciaContext):
        try:
            exprs = ctx.expr()
            if len(exprs) >= 2:
                cond_expr = exprs[1]
                cond_type = self._map_type(self._infer_expr_type(cond_expr))
                if cond_type != "bool":
                    self._error(cond_expr, f"La condición en un ciclo 'para' debe ser de tipo 'bool'. Actualmente es '{cond_type}'.")
            else:
                self._warn(ctx, "El ciclo 'para' no tiene una condición explícita. Se ejecutará como bucle infinito si no hay control.")
        except Exception as e:
            self._error(ctx, f"Error al validar la condición del ciclo 'para': {e}")

    def enterFuncionDef(self, ctx: LenParser.FuncionDefContext):
        scope = self.scopes[-1]
        name = ctx.ID().getText()
        return_type = self._map_type(ctx.tipo().getText()) if ctx.tipo() else "void"

        if name not in scope.functions:
            params = []
            if ctx.params() and hasattr(ctx.params(), "param"):
                for p in ctx.params().param():
                    tipo = self._map_type(p.tipo().getText())
                    ident = p.ID().getText()
                    params.append((ident, tipo))
            scope.functions[name] = (return_type, params)

        _, params = scope.functions[name]
        self.current_function_return_type = return_type
        self.scopes.append(Scope())
        for ident, tipo in params:
            self._declare_variable(ctx, ident, tipo)

    def exitFuncionDef(self, ctx: LenParser.FuncionDefContext):
        self.scopes.pop()
        if self.current_function_return_type != "void":
            if not self._has_guaranteed_return(ctx.bloque()):
                self._error(ctx, f"La función '{ctx.ID().getText()}' de tipo '{self.current_function_return_type}' no garantiza un retorno en todos los caminos posibles.")
        self.current_function_return_type = None

    def exitDeclaracionGlobalSimple(self, ctx: LenParser.DeclaracionGlobalSimpleContext):
        tipo = self._map_type(ctx.tipo().getText())
        ident = ctx.ID().getText()
        self._declare_variable(ctx, ident, tipo)

    def exitDeclaracionSimple(self, ctx: LenParser.DeclaracionSimpleContext):
        tipo = self._map_type(ctx.tipo().getText())
        ident = ctx.ID().getText()
        expr_type = self._map_type(self._infer_expr_type(ctx.expr())) if ctx.expr() else None

        if expr_type and not self._is_compatible_assignment(tipo, expr_type):
            self._error(ctx, f"Incompatibilidad de tipos en inicialización de '{ident}': se declaró como '{tipo}' pero se asignó valor de tipo '{expr_type}'.")

        self._declare_variable(ctx, ident, tipo)
        if ctx.expr():
            self._mark_assigned(ident)

    def exitDeclaracionInferida(self, ctx: LenParser.DeclaracionInferidaContext):
        ident = ctx.ID().getText()
        if not ctx.expr():
            self._error(ctx, f"La variable '{ident}' declarada con inferencia requiere una expresión para deducir su tipo.")
        tipo = self._map_type(self._infer_expr_type(ctx.expr()))
        self._declare_variable(ctx, ident, tipo)
        self._mark_assigned(ident)

    def exitAsignacionExp(self, ctx: LenParser.AsignacionExpContext):
        name = ctx.ID().getText()
        expr_type = self._map_type(self._infer_expr_type(ctx.asignacion()))
        var_type = self._resolve_variable_type(ctx, name)

        if not self._is_compatible_assignment(var_type, expr_type):
            self._error(ctx, f"Incompatibilidad de tipos en asignación a '{name}': tipo esperado '{var_type}', recibido '{expr_type}'.")

        self._mark_assigned(name)

    def exitMOSTRARSentencia(self, ctx: LenParser.MOSTRARSentenciaContext):
        if ctx.args():
            for expr in ctx.args().expr():
                self._infer_expr_type(expr)
                self._marcar_leidas(expr)

    def _marcar_leidas(self, ctx):
        if hasattr(ctx, "ID") and ctx.ID():
            name = ctx.ID().getText()
            for scope in reversed(self.scopes):
                if name in scope.variables:
                    scope.variables[name]["read"] = True
                    return
            if name in self.scopes[0].functions:
                return
            self._error(ctx, f"La variable '{name}' fue usada pero no ha sido declarada en ningún ámbito visible.")
        for i in range(ctx.getChildCount()):
            child = ctx.getChild(i)
            if isinstance(child, ParserRuleContext):
                self._marcar_leidas(child)

    def check_funciones_no_usadas(self):
        for scope in self.scopes:
            for name in scope.functions:
                if name not in self.called_functions:
                    ctx = scope.functions[name][2] if len(scope.functions[name]) > 2 else None
                    self._warn(ctx, f"La función '{name}' fue declarada pero no se utilizó en ninguna parte del programa.")

    def exitRetornarSentencia(self, ctx: LenParser.RetornarSentenciaContext):
        if self.current_function_return_type is None:
            self._error(ctx, "Uso inválido de 'ret': esta sentencia solo puede estar dentro de una función.")
        
        expr_type = "void"
        if ctx.expr():
            expr_type = self._map_type(self._infer_expr_type(ctx.expr()))
            self._marcar_leidas(ctx.expr())

        if expr_type != self.current_function_return_type:
            self._error(ctx, f"Tipo de retorno inválido: la función espera '{self.current_function_return_type}', pero se está retornando '{expr_type}'.")

    def _declare_variable(self, ctx, name, tipo):
        if name in self.scopes[-1].variables:
            self._error(ctx, f"La variable '{name}' ya fue declarada en este mismo bloque.")
        self.scopes[-1].variables[name] = {"type": tipo, "assigned": False, "read": False, "ctx": ctx}

    def _mark_assigned(self, name):
        for scope in reversed(self.scopes):
            if name in scope.variables:
                scope.variables[name]["assigned"] = True
                return

    def _resolve_variable_type(self, ctx, name):
        for scope in reversed(self.scopes):
            if name in scope.variables:
                scope.variables[name]["read"] = True
                return scope.variables[name]["type"]
        self._error(ctx, f"La variable '{name}' no fue declarada antes de su uso.")

    def _infer_expr_type(self, ctx):
        if ctx is None:
            return "void"
        if hasattr(ctx, "NUMERO") and ctx.NUMERO():
            text = ctx.NUMERO().getText()
            return "decimal" if '.' in text else "entero"
        if hasattr(ctx, "BOOL_LIT") and ctx.BOOL_LIT():
            return "bool"
        if hasattr(ctx, "TEXTO") and ctx.TEXTO():
            return "cadena"
        if ctx.getChildCount() >= 2 and ctx.getChild(1).getText() == '(':
            name = ctx.getChild(0).getText()
            args_ctx = ctx.getChild(2) if ctx.getChildCount() >= 3 else None
            args = args_ctx.expr() if hasattr(args_ctx, "expr") else []
            return self._check_function_call(ctx, name, args)
        if hasattr(ctx, "ID") and ctx.ID():
            return self._resolve_variable_type(ctx, ctx.ID().getText())
        if ctx.getChildCount() == 3:
            left = ctx.getChild(0)
            op = ctx.getChild(1).getText()
            right = ctx.getChild(2)
            tipo_izq = self._infer_expr_type(left)
            tipo_der = self._infer_expr_type(right)
            if op in ["<", ">", "<=", ">=", "==", "!="]:
                return "bool"
            if op in ["&&", "||"]:
                if tipo_izq == "bool" and tipo_der == "bool":
                    return "bool"
                else:
                    self._error(ctx, f"Operador lógico '{op}' requiere valores booleanos. Se recibió '{tipo_izq}' y '{tipo_der}'.")
                    return "bool"
            if op == "+" and tipo_izq == "cadena" and tipo_der == "cadena":
                return "cadena"
            if op in ["+", "-", "*", "/", "^", "%"]:
                if "decimal" in [tipo_izq, tipo_der]:
                    return "decimal" if op != "%" else "entero"
                return "entero"
        if ctx.getChildCount() == 2 and ctx.getChild(0).getText() == "!":
            tipo = self._infer_expr_type(ctx.getChild(1))
            if tipo != "bool":
                self._error(ctx, f"El operador '!' requiere un valor booleano. Se recibió '{tipo}'.")
            return "bool"
        if ctx.getChildCount() == 1:
            return self._infer_expr_type(ctx.getChild(0))
        if hasattr(ctx, "expr") and callable(ctx.expr):
            return self._infer_expr_type(ctx.expr())
        return "entero"

    def _check_function_call(self, ctx, name, args):
        if name in self.scopes[0].functions:
            return_type, expected_params = self.scopes[0].functions[name]
        else:
            for scope in reversed(self.scopes):
                if name in scope.functions:
                    return_type, expected_params = scope.functions[name]
                    break
            else:
                self._error(ctx, f"La función '{name}' fue llamada pero no está definida en el programa.")
                return "entero"
        if len(args) != len(expected_params):
            self._error(ctx, f"La función '{name}' requiere {len(expected_params)} argumento(s), pero se proporcionaron {len(args)}.")
            return return_type
        for i, (arg_expr, (param_name, expected_type)) in enumerate(zip(args, expected_params)):
            actual_type = self._map_type(self._infer_expr_type(arg_expr))
            if actual_type != expected_type:
                self._error(arg_expr, f"Argumento {i+1} inválido en llamada a '{name}': se esperaba '{expected_type}', pero se recibió '{actual_type}'.")
        return return_type

    def _has_guaranteed_return(self, ctx):
        if ctx is None:
            return False
        class_name = ctx.__class__.__name__
        if class_name == "RetornarSentenciaContext":
            return True
        if class_name == "SiSentenciaContext":
            if not ctx.SINO():
                return False
            return self._has_guaranteed_return(ctx.sentencia(0)) and self._has_guaranteed_return(ctx.sentencia(1))
        if hasattr(ctx, "sentencia") and callable(ctx.sentencia):
            sentencias = ctx.sentencia()
            if sentencias:
                return self._has_guaranteed_return(sentencias[-1])
            return False
        if hasattr(ctx, "bloque") and callable(ctx.bloque):
            return self._has_guaranteed_return(ctx.bloque())
        if ctx.getChildCount() == 1 and isinstance(ctx.getChild(0), ParserRuleContext):
            return self._has_guaranteed_return(ctx.getChild(0))
        return False

    def _error(self, ctx, msg):
        line = ctx.start.line if ctx.start else "desconocida"
        raise SemanticError(f"[Línea {line}] Error semántico: {msg}")

    def _warn(self, ctx, msg):
        line = ctx.start.line if ctx.start else "desconocida"
        print(f"[Línea {line}] Advertencia: {msg}")

    def pre_register_functions(self, funciones_node):
        if not funciones_node:
            return

        global_scope = self.scopes[0]  # ámbito global

        for i in range(funciones_node.getChildCount()):
            child = funciones_node.getChild(i)
            if isinstance(child, LenParser.FuncionDefContext):
                name = child.ID().getText()
                return_type = self._map_type(child.tipo().getText()) if child.tipo() else "void"
                params = []

                if child.params() and hasattr(child.params(), "param"):
                    for p in child.params().param():
                        tipo = self._map_type(p.tipo().getText())
                        ident = p.ID().getText()
                        params.append((ident, tipo))

                if name in global_scope.functions:
                    self._error(child, f"La función '{name}' ya fue definida anteriormente.")
                else:
                    global_scope.functions[name] = (return_type, params)
