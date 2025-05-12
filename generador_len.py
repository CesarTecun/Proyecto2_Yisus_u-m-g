from llvmlite import ir
import llvmlite.binding as llvm

class LLVMGeneratorLen:
    def __init__(self):
        self.module = ir.Module(name="len_module")
        self.module.triple = llvm.get_default_triple()  # ← ESTA LÍNEA
        self.builder = None
        self.funcs = {}
        self.variables = {}
        self.printf = self.declare_printf()
        self.fflush = self.declare_fflush()
        self.string_constants = {}
        self.concat_fn = None
        self.declare_string_helpers()



    def declare_printf(self):
        voidptr_ty = ir.IntType(8).as_pointer()
        printf_ty = ir.FunctionType(ir.IntType(32), [voidptr_ty], var_arg=True)
        return ir.Function(self.module, printf_ty, name="printf")
    

    def generate(self, node):
        if node.type == "Program":
            return self.handle_program(node)
        elif node.type == "Block":
            return self.handle_block(node)
        elif node.type == "GlobalDeclaration":
            return self.handle_global_declaration(node)
        elif node.type == "Declaration":
            return self.handle_declaration(node)
        elif node.type == "Function":
            return self.handle_function(node)
        elif node.type == "Print":
            return self.handle_print(node)
        elif node.type == "If":
            return self.handle_if(node)
        elif node.type == "While":
            return self.handle_while(node)
        elif node.type == "Assign":
            return self.handle_assign(node)
        elif node.type == "DoWhile":
            return self.handle_do_while(node)
        elif node.type == "For":
            return self.handle_for(node)
        elif node.type == "Return":
            return self.handle_return(node)
        elif node.type == "InferredDeclaration":
            return self.handle_inferred_declaration(node)
        elif node.type == "FunctionCall":
            return self.handle_function_call(node)
        elif node.type == "Functions":
            for func in node.children:
                self.generate(func)
        else:
            raise Exception(f"⚠️ Nodo no soportado en generate: {node.type}")
        
    def handle_inferred_declaration(self, node):
        nombre = node.value
        expr = node.children[0]
        val = self.generate_expr(expr)
        ptr = self.builder.alloca(val.type, name=nombre)
        self.builder.store(val, ptr)
        self.variables[nombre] = ptr


    def handle_function_call(self, node):
        func = self.funcs.get(node.value)
        if func is None:
            raise Exception(f"Función '{node.value}' no declarada")

        arg_vals = [self.generate_expr(arg) for arg in node.children]
        param_types = list(func.function_type.args)
        final_args = []

        for val, expected_type in zip(arg_vals, param_types):
            if val.type != expected_type:
                if val.type == ir.IntType(32) and expected_type == ir.DoubleType():
                    val = self.builder.sitofp(val, ir.DoubleType())
                elif val.type == ir.DoubleType() and expected_type == ir.IntType(32):
                    val = self.builder.fptosi(val, ir.IntType(32))
                elif val.type == ir.IntType(1) and expected_type == ir.IntType(32):
                    val = self.builder.zext(val, ir.IntType(32))
                elif val.type == ir.IntType(32) and expected_type == ir.IntType(1):
                    val = self.builder.trunc(val, ir.IntType(1))
                else:
                    raise Exception(f"Incompatibilidad de tipos en argumentos: {val.type} vs {expected_type}")
            final_args.append(val)

        return self.builder.call(func, final_args)

    def handle_return(self, node):
        if node.children:
            val = self.generate_expr(node.children[0])
            self.builder.ret(val)
        else:
            self.builder.ret_void()
       
        
    def handle_for(self, node):
        init, cond_expr, step_expr, cuerpo = node.children

        # Ejecutar inicialización
        self.generate(init)

        cond_bb = self.builder.append_basic_block("for_cond")
        body_bb = self.builder.append_basic_block("for_body")
        step_bb = self.builder.append_basic_block("for_step")
        after_bb = self.builder.append_basic_block("for_end")

        self.builder.branch(cond_bb)

        self.builder.position_at_start(cond_bb)
        cond = self.generate_expr(cond_expr)

        if cond.type == ir.DoubleType():
            cond = self.builder.fcmp_ordered("!=", cond, ir.Constant(ir.DoubleType(), 0.0))
        elif cond.type == ir.IntType(32):
            cond = self.builder.icmp_signed("!=", cond, ir.Constant(ir.IntType(32), 0))

        self.builder.cbranch(cond, body_bb, after_bb)

        self.builder.position_at_start(body_bb)
        self.generate(cuerpo)
        if self.builder.block.terminator is None:
            self.builder.branch(step_bb)

        self.builder.position_at_start(step_bb)
        self.generate(step_expr)
        if self.builder.block.terminator is None:
            self.builder.branch(cond_bb)

        self.builder.position_at_start(after_bb)

        
    def handle_do_while(self, node):
        body_bb = self.builder.append_basic_block("do_body")
        cond_bb = self.builder.append_basic_block("do_cond")
        after_bb = self.builder.append_basic_block("do_end")

        self.builder.branch(body_bb)

        self.builder.position_at_start(body_bb)
        self.generate(node.children[0])  # cuerpo
        if self.builder.block.terminator is None:
            self.builder.branch(cond_bb)

        self.builder.position_at_start(cond_bb)
        cond = self.generate_expr(node.children[1])

        if cond.type == ir.DoubleType():
            cond = self.builder.fcmp_ordered("!=", cond, ir.Constant(ir.DoubleType(), 0.0))
        elif cond.type == ir.IntType(32):
            cond = self.builder.icmp_signed("!=", cond, ir.Constant(ir.IntType(32), 0))
        elif cond.type != ir.IntType(1):
            raise Exception(f"Tipo no soportado para condición: {cond.type}")

        self.builder.cbranch(cond, body_bb, after_bb)

        self.builder.position_at_start(after_bb)


    def handle_assign(self, node):
        nombre = node.value
        if nombre not in self.variables:
            raise Exception(f"Variable '{nombre}' no declarada")
        ptr = self.variables[nombre]
        val = self.generate_expr(node.children[0])
        self.builder.store(val, ptr)


    def handle_program(self, node):
        func_type = ir.FunctionType(ir.VoidType(), [])
        main_func = ir.Function(self.module, func_type, name="main")
        main_block = main_func.append_basic_block(name="entry")

        saved_builder = self.builder
        saved_variables = self.variables

        # Paso 1: Generar declaraciones globales primero
        for child in node.children:
            if child.type == "GlobalDeclaration":
                self.generate(child)

        # Paso 2-A: Pre-registro de firmas de funciones
        for child in node.children:
            if child.type == "Functions":
                for func_node in child.children:
                    nombre = func_node.value["nombre"]
                    tipo_retorno = self.map_type(func_node.value["tipo"])
                    args = [self.map_type(p.value["tipo"]) for p in func_node.children if p.type == "Param"]
                    func_type = ir.FunctionType(tipo_retorno, args)
                    func = ir.Function(self.module, func_type, name=nombre)
                    self.funcs[nombre] = func

        # Paso 2-B: Generar funciones completas
        for child in node.children:
            if child.type == "Functions":
                for func_node in child.children:
                    self.generate(func_node)

        # Paso 3: Generar el cuerpo principal
        self.builder = ir.IRBuilder(main_block)
        self.variables = self.variables.copy()

        for child in node.children:
            if child.type not in ["Functions", "GlobalDeclaration"]:
                self.generate(child)

        if self.builder.block.terminator is None:
            self.builder.ret_void()

        self.builder = saved_builder
        self.variables = saved_variables

        return str(self.module)



    
    def handle_block(self, node):
        for stmt in node.children:
            self.generate(stmt)

    def handle_declaration(self, node):
        tipo = node.value["tipo"]
        nombre = node.value["nombre"]
        ir_type = self.map_type(tipo)
        ptr = self.builder.alloca(ir_type, name=nombre)

        if node.children:
            val = self.generate_expr(node.children[0])
            if val.type != ptr.type.pointee:
                if val.type == ir.IntType(32) and ptr.type.pointee == ir.DoubleType():
                    val = self.builder.sitofp(val, ir.DoubleType())
                elif val.type == ir.DoubleType() and ptr.type.pointee == ir.IntType(32):
                    val = self.builder.fptosi(val, ir.IntType(32))
                elif val.type == ir.IntType(1) and ptr.type.pointee == ir.IntType(32):
                    val = self.builder.zext(val, ir.IntType(32))
                elif val.type == ir.IntType(32) and ptr.type.pointee == ir.IntType(1):
                    val = self.builder.trunc(val, ir.IntType(1))
                else:
                    raise Exception(f"Tipo incompatible en declaración: {val.type} → {ptr.type.pointee}")
            self.builder.store(val, ptr)


        self.variables[nombre] = ptr

    def handle_if(self, node):
        cond = self.generate_expr(node.children[0])

        # Normalizar condición a booleano
        if cond.type == ir.DoubleType():
            cond = self.builder.fcmp_ordered("!=", cond, ir.Constant(ir.DoubleType(), 0.0))
        elif cond.type == ir.IntType(32):
            cond = self.builder.icmp_signed("!=", cond, ir.Constant(ir.IntType(32), 0))
        elif cond.type != ir.IntType(1):
            raise Exception(f"Tipo no soportado para condición: {cond.type}")

        then_bb = self.builder.append_basic_block("if_then")
        else_bb = self.builder.append_basic_block("if_else") if len(node.children) == 3 else None
        merge_bb = self.builder.append_basic_block("if_merge")

        # ✅ Verificar si el bloque actual ya tiene terminador antes de cbranch
        if self.builder.block.terminator is None:
            self.builder.cbranch(cond, then_bb, else_bb if else_bb else merge_bb)

        # THEN
        self.builder.position_at_start(then_bb)
        self.generate(node.children[1])
        if self.builder.block.terminator is None:
            self.builder.branch(merge_bb)

        # ELSE
        if else_bb:
            self.builder.position_at_start(else_bb)
            self.generate(node.children[2])
            if self.builder.block.terminator is None:
                self.builder.branch(merge_bb)

        # MERGE
        self.builder.position_at_start(merge_bb)


    def handle_while(self, node):
        cond_expr = node.children[0]
        cuerpo = node.children[1]

        loop_bb = self.builder.append_basic_block("while_cond")
        body_bb = self.builder.append_basic_block("while_body")
        after_bb = self.builder.append_basic_block("while_end")

        self.builder.branch(loop_bb)

        self.builder.position_at_start(loop_bb)
        cond = self.generate_expr(cond_expr)

        if cond.type == ir.DoubleType():
            cond = self.builder.fcmp_ordered("!=", cond, ir.Constant(ir.DoubleType(), 0.0))
        elif cond.type == ir.IntType(32):
            cond = self.builder.icmp_signed("!=", cond, ir.Constant(ir.IntType(32), 0))
        elif cond.type != ir.IntType(1):
            raise Exception(f"Tipo no soportado para condición de loop: {cond.type}")

        self.builder.cbranch(cond, body_bb, after_bb)

        self.builder.position_at_start(body_bb)
        self.generate(cuerpo)
        if self.builder.block.terminator is None:
            self.builder.branch(loop_bb)

        self.builder.position_at_start(after_bb)


    def handle_global_declaration(self, node):
        tipo = node.value["tipo"]
        nombre = node.value["nombre"]
        ir_type = self.map_type(tipo)
        var = ir.GlobalVariable(self.module, ir_type, name=nombre)
        var.linkage = "internal" 


        if node.children:
            val = self.generate_expr(node.children[0])
            if isinstance(val, ir.Constant):
                var.initializer = val
            else:
                raise Exception("Inicialización global debe ser con una constante")
        else:
            var.initializer = ir_type(0)

        self.variables[nombre] = var


    def handle_function(self, node):
        nombre = node.value["nombre"]
        tipo_retorno = self.map_type(node.value["tipo"])
        args = [self.map_type(p.value["tipo"]) for p in node.children if p.type == "Param"]
        arg_nombres = [p.value["nombre"] for p in node.children if p.type == "Param"]

        # ✅ Recuperar función pre-registrada (no volver a crearla)
        func = self.funcs[nombre]

        block = func.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(block)

        local_vars = self.variables.copy()  # incluir variables globales
        self.variables = local_vars

        for i, arg in enumerate(func.args):
            arg.name = arg_nombres[i]
            ptr = self.builder.alloca(arg.type, name=arg.name)
            self.builder.store(arg, ptr)
            self.variables[arg.name] = ptr

        cuerpo = node.children[-1]
        self.generate_block(cuerpo)

        if self.builder.block.terminator is None:
            if isinstance(func.function_type.return_type, ir.VoidType):
                self.builder.ret_void()
            else:
                self.builder.ret(func.function_type.return_type(0))

    def declare_fflush(self):
        voidptr_ty = ir.IntType(8).as_pointer()
        fflush_ty = ir.FunctionType(ir.IntType(32), [voidptr_ty])
        return ir.Function(self.module, fflush_ty, name="fflush")

    def generate_block(self, node):
        for stmt in node.children:
            self.generate(stmt)

    def handle_print(self, node):
        if not node.children:
            # Caso especial: mst(); → línea vacía
            fmt_str = "\n\0"
            var_name = f"fstr_empty"
            if var_name not in self.module.globals:
                fmt_global = ir.GlobalVariable(
                    self.module,
                    ir.ArrayType(ir.IntType(8), len(fmt_str)),
                    name=var_name
                )
                fmt_global.linkage = "internal"
                fmt_global.global_constant = True
                fmt_global.initializer = ir.Constant(
                    fmt_global.type.pointee,
                    bytearray(fmt_str.encode("utf-8"))
                )
            fmt_ptr = self.builder.bitcast(self.module.globals[var_name], ir.IntType(8).as_pointer())
            self.builder.call(self.printf, [fmt_ptr])

            # 🔄 Forzar impresión inmediata
            null_ptr = ir.Constant(ir.IntType(8).as_pointer(), None)
            self.builder.call(self.fflush, [null_ptr])
            return

        for expr in node.children:
            val = self.generate_expr(expr)

            if isinstance(val.type, ir.PointerType) and val.type.pointee == ir.IntType(8):  # cadena
                fmt_str = "%s\n\0"
            elif val.type == ir.IntType(32):
                fmt_str = "%d\n\0"
            elif val.type == ir.DoubleType():
                fmt_str = "%f\n\0"
            elif val.type == ir.IntType(1):
                fmt_str = "%d\n\0"
            else:
                raise Exception(f"Tipo no soportado para impresión: {val.type}")

            unique_name = f"fstr_{id(expr)}"
            fmt_global = ir.GlobalVariable(
                self.module,
                ir.ArrayType(ir.IntType(8), len(fmt_str)),
                name=unique_name
            )
            fmt_global.linkage = "internal"
            fmt_global.global_constant = True
            fmt_global.initializer = ir.Constant(
                fmt_global.type.pointee,
                bytearray(fmt_str.encode("utf-8"))
            )

            fmt_ptr = self.builder.bitcast(fmt_global, ir.IntType(8).as_pointer())
            self.builder.call(self.printf, [fmt_ptr, val])

            # 🔄 Forzar impresión inmediata
            null_ptr = ir.Constant(ir.IntType(8).as_pointer(), None)
            self.builder.call(self.fflush, [null_ptr])



    def define_concat_function(self):
        if self.concat_fn:
            return self.concat_fn

        i8ptr = ir.IntType(8).as_pointer()
        func_ty = ir.FunctionType(i8ptr, [i8ptr, i8ptr])
        fn = ir.Function(self.module, func_ty, name="concat")
        entry = fn.append_basic_block("entry")
        builder = ir.IRBuilder(entry)

        # Simulación: solo retorna el primer argumento por ahora
        builder.ret(fn.args[0])

        self.concat_fn = fn
        return fn

    def generate_expr(self, node):
        if node is None:
            raise Exception("Error: nodo es None")

        if node.type == "Literal":
            return self.handle_literal(node.value)

        elif node.type == "Variable":
            return self.handle_variable(node.value)

        elif node.type == "BinaryOp":
            lhs = self.generate_expr(node.children[0])
            rhs = self.generate_expr(node.children[1])
            lhs, rhs = self.promote_types(lhs, rhs)
            return self.handle_binary_op(node.value, lhs, rhs)

        elif node.type == "UnaryOp":
            operand = self.generate_expr(node.children[0])
            if node.value == "not":
                if operand.type != ir.IntType(1):
                    raise Exception(f"'not' requiere tipo booleano (i1), pero se recibió: {operand.type}")
                return self.builder.not_(operand)
            elif node.value == "+":
                return operand  # no-op
            elif node.value == "-":
                zero = ir.Constant(operand.type, 0)
                return self.builder.fsub(zero, operand) if operand.type == ir.DoubleType() else self.builder.sub(zero, operand)
            else:
                raise Exception(f"Operador unario no soportado: {node.value}")

        elif node.type == "FunctionCall":
            return self.handle_function_call(node)

        raise Exception(f"No se pudo generar código para el nodo: {node}")

    def handle_literal(self, value):
        if isinstance(value, bool):
            return ir.Constant(ir.IntType(1), int(value))
        elif isinstance(value, int):
            return ir.Constant(ir.IntType(32), value)
        elif isinstance(value, float):
            return ir.Constant(ir.DoubleType(), value)
        elif isinstance(value, str):
            # Verifica si ya fue definido este literal
            if value in self.string_constants:
                global_str = self.string_constants[value]
            else:
                str_bytes = bytearray(value.encode("utf8")) + b"\00"
                str_type = ir.ArrayType(ir.IntType(8), len(str_bytes))

                var_name = f"str_{abs(hash(value)) % (10**8)}"
                # Evitar colisiones por nombre duplicado
                while var_name in self.module.globals:
                    var_name += "_x"

                global_str = ir.GlobalVariable(self.module, str_type, name=var_name)
                global_str.linkage = "internal"
                global_str.global_constant = True
                global_str.initializer = ir.Constant(str_type, str_bytes)

                self.string_constants[value] = global_str

            return self.builder.bitcast(global_str, ir.IntType(8).as_pointer())

        else:
            raise Exception(f"Tipo de literal no soportado: {type(value)}")

    def handle_variable(self, name):
        if name not in self.variables:
            raise Exception(f"Variable '{name}' no declarada")
        ptr = self.variables[name]
        return self.builder.load(ptr)

    def promote_types(self, lhs, rhs):
        # Si ambos tipos ya son iguales, no se hace nada
        if lhs.type == rhs.type:
            return lhs, rhs

        # Promoción entre int y float
        if lhs.type == ir.IntType(32) and rhs.type == ir.DoubleType():
            lhs = self.builder.sitofp(lhs, ir.DoubleType())
            return lhs, rhs
        elif lhs.type == ir.DoubleType() and rhs.type == ir.IntType(32):
            rhs = self.builder.sitofp(rhs, ir.DoubleType())
            return lhs, rhs

        #Evitar conversión entre booleanos y otros tipos
        if lhs.type == ir.IntType(1) or rhs.type == ir.IntType(1):
            raise Exception(f"No se puede promover tipos booleanos en operación mixta: {lhs.type}, {rhs.type}")

        raise Exception(f"Tipos incompatibles: {lhs.type}, {rhs.type}")


    def handle_binary_op(self, op, lhs, rhs):
        # Aritméticos
        if op == "+":
            if lhs.type == ir.PointerType(ir.IntType(8)) and rhs.type == ir.PointerType(ir.IntType(8)):
                concat_fn = self.define_concat_function()
                return self.builder.call(concat_fn, [lhs, rhs])
            return self.builder.fadd(lhs, rhs) if lhs.type == ir.DoubleType() else self.builder.add(lhs, rhs)
        elif op == "-":
            return self.builder.fsub(lhs, rhs) if lhs.type == ir.DoubleType() else self.builder.sub(lhs, rhs)
        elif op == "*":
            return self.builder.fmul(lhs, rhs) if lhs.type == ir.DoubleType() else self.builder.mul(lhs, rhs)
        elif op == "/":
            return self.builder.fdiv(lhs, rhs) if lhs.type == ir.DoubleType() else self.builder.sdiv(lhs, rhs)
        elif op == "%":
            return self.builder.frem(lhs, rhs) if lhs.type == ir.DoubleType() else self.builder.srem(lhs, rhs)
        elif op == "^":
            return self.handle_power(lhs, rhs)

        # Relacionales
        elif op == "<":
            return self.builder.fcmp_ordered("<", lhs, rhs) if lhs.type == ir.DoubleType() else self.builder.icmp_signed("<", lhs, rhs)
        elif op == "<=":
            return self.builder.fcmp_ordered("<=", lhs, rhs) if lhs.type == ir.DoubleType() else self.builder.icmp_signed("<=", lhs, rhs)
        elif op == ">":
            return self.builder.fcmp_ordered(">", lhs, rhs) if lhs.type == ir.DoubleType() else self.builder.icmp_signed(">", lhs, rhs)
        elif op == ">=":
            return self.builder.fcmp_ordered(">=", lhs, rhs) if lhs.type == ir.DoubleType() else self.builder.icmp_signed(">=", lhs, rhs)
        elif op == "==":
            return self.builder.fcmp_ordered("==", lhs, rhs) if lhs.type == ir.DoubleType() else self.builder.icmp_signed("==", lhs, rhs)
        elif op == "!=":
            return self.builder.fcmp_ordered("!=", lhs, rhs) if lhs.type == ir.DoubleType() else self.builder.icmp_signed("!=", lhs, rhs)

        # Booleanos
        elif op == "and":
            if lhs.type == ir.IntType(1) and rhs.type == ir.IntType(1):
                return self.builder.and_(lhs, rhs)
            else:
                raise Exception(f"'and' requiere booleanos: {lhs.type}, {rhs.type}")
        elif op == "or":
            if lhs.type == ir.IntType(1) and rhs.type == ir.IntType(1):
                return self.builder.or_(lhs, rhs)
            else:
                raise Exception(f"'or' requiere booleanos: {lhs.type}, {rhs.type}")

        else:
            raise Exception(f"Operador binario no soportado: {op}")



    def handle_power(self, lhs, rhs):
        if lhs.type == ir.DoubleType():
            # pow para flotantes usando la intrínseca de LLVM
            pow_fn = self.module.globals.get("llvm.pow.f64")
            if pow_fn is None:
                pow_ty = ir.FunctionType(ir.DoubleType(), [ir.DoubleType(), ir.DoubleType()])
                pow_fn = ir.Function(self.module, pow_ty, name="llvm.pow.f64")
            return self.builder.call(pow_fn, [lhs, rhs])
        
        elif lhs.type == ir.IntType(32):
            result = self.builder.alloca(ir.IntType(32), name="pow_result")
            self.builder.store(ir.Constant(ir.IntType(32), 1), result)

            counter = self.builder.alloca(ir.IntType(32), name="pow_i")
            self.builder.store(ir.Constant(ir.IntType(32), 0), counter)

            cond_bb = self.builder.append_basic_block("pow_cond")
            body_bb = self.builder.append_basic_block("pow_body")
            end_bb = self.builder.append_basic_block("pow_end")

            self.builder.branch(cond_bb)

            self.builder.position_at_start(cond_bb)
            i_val = self.builder.load(counter)
            cond = self.builder.icmp_signed("<", i_val, rhs)
            self.builder.cbranch(cond, body_bb, end_bb)

            self.builder.position_at_start(body_bb)
            res_val = self.builder.load(result)
            mult = self.builder.mul(res_val, lhs)
            self.builder.store(mult, result)
            next_i = self.builder.add(i_val, ir.Constant(ir.IntType(32), 1))
            self.builder.store(next_i, counter)
            self.builder.branch(cond_bb)

            self.builder.position_at_start(end_bb)
            return self.builder.load(result)
        
        else:
            raise Exception(f"Tipo no soportado para operador ^: {lhs.type}")

    def map_type(self, tipo):
        tipo = tipo.lower()  # asegurar que esté en minúsculas

        if tipo in ["int", "entero"]:
            return ir.IntType(32)
        elif tipo in ["flt", "decimal"]:
            return ir.DoubleType()
        elif tipo in ["bool", "bol"]:
            return ir.IntType(1)
        elif tipo in ["str", "cadena"]:
            return ir.PointerType(ir.IntType(8))  # para cadenas tipo char*
        elif tipo in ["void", "vd"]:
            return ir.VoidType()
        else:
            raise Exception(f"Tipo no soportado: {tipo}")
        

    def define_concat_function(self):
        if "concat" in self.funcs:
            return self.funcs["concat"]  # Ya existe

        i8ptr = ir.IntType(8).as_pointer()
        i64 = ir.IntType(64)

        func_ty = ir.FunctionType(i8ptr, [i8ptr, i8ptr])
        func = ir.Function(self.module, func_ty, name="concat")
        self.funcs["concat"] = func

        block = func.append_basic_block(name="entry")
        builder = ir.IRBuilder(block)

        str1, str2 = func.args

        len1 = builder.call(self.strlen, [str1])
        len2 = builder.call(self.strlen, [str2])
        total_len = builder.add(builder.add(len1, len2), ir.Constant(i64, 1))

        new_str = builder.call(self.malloc, [total_len])
        builder.call(self.memcpy, [new_str, str1, len1])
        offset_ptr = builder.gep(new_str, [len1])
        builder.call(self.memcpy, [offset_ptr, str2, len2])

        final_null = builder.gep(new_str, [builder.add(len1, len2)])
        builder.store(ir.Constant(ir.IntType(8), 0), final_null)

        builder.ret(new_str)
        return func

    def declare_string_helpers(self):
        i8ptr = ir.IntType(8).as_pointer()
        i64 = ir.IntType(64)

        # malloc: i8* malloc(i64)
        malloc_ty = ir.FunctionType(i8ptr, [i64])
        self.malloc = ir.Function(self.module, malloc_ty, name="malloc")

        # strlen: i64 strlen(i8*)
        strlen_ty = ir.FunctionType(i64, [i8ptr])
        self.strlen = ir.Function(self.module, strlen_ty, name="strlen")

        # memcpy: i8* memcpy(i8* dest, i8* src, i64 n)
        memcpy_ty = ir.FunctionType(i8ptr, [i8ptr, i8ptr, i64])
        self.memcpy = ir.Function(self.module, memcpy_ty, name="memcpy")
