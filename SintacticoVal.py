from difflib import get_close_matches
import re

def limpiar_strings(linea):
    return re.sub(r'"[^"]*"', '', linea)

def validar_parentesis_vacios(input_file):
    errores = []
    estructuras = {'loop', 'para', 'si', 'mostrar'}  # ajusta según tu gramática

    with open(input_file, "r") as f:
        for line_num, line in enumerate(f, 1):
            linea = line.strip().lower()
            if any(linea.startswith(e + ' ()') or f"{e}()" in linea for e in estructuras):
                errores.append(f"[Línea {line_num}] Error: La estructura '{linea.split('(')[0]}' no puede tener paréntesis vacíos.")
    return errores

def sugerir_palabras_clave_invalidas(ruta_archivo):
    palabras_reservadas = {
        'prog', 'ini', 'end', 'si', 'no', 'loop', 'para', 'ret', 'mst', 'mostrar',
        'int', 'flt', 'bool', 'str', 'aut', 'vd', 'funs', 'void', 'do', 'fin'
    }
    errores = []

    with open(ruta_archivo, "r") as file:
        for line_num, line in enumerate(file, 1):
            tokens = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', line)
            for token in tokens:
                if token not in palabras_reservadas:
                    sugerencias = get_close_matches(token, palabras_reservadas, n=1, cutoff=0.85)
                    if sugerencias:
                        errores.append(
                            f"[Línea {line_num}] Posible error de palabra clave: '{token}'. ¿Quiso decir '{sugerencias[0]}'?"
                        )
    return errores


def validar_llamadas_invalidas(input_file):
    errores = []

    patron_def_func = re.compile(r'^\s*(int|flt|bol|str|aut|vd|void)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(')
    patron_llamada_func = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(')

    funciones_builtin = {"mst"}
    palabras_clave = {
        'si', 'no', 'loop', 'para', 'ret', 'mostrar', 'ini', 'fin', 'funs', 'hacer',
        'int', 'flt', 'bol', 'str', 'aut', 'vd', 'void', 'program', 'for'
    }

    funciones_definidas = set()
    llamadas = []

    brace_stack = []
    inside_funs_block = False

    with open(input_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            linea = line.strip()
            if not linea or linea.startswith("#"):
                continue

            if linea.lower().startswith("funs"):
                inside_funs_block = True

            if "{" in linea:
                brace_stack.append("{")
            if "}" in linea and brace_stack:
                brace_stack.pop()
                if inside_funs_block and not brace_stack:
                    inside_funs_block = False

            if inside_funs_block:
                match_def = patron_def_func.match(linea)
                if match_def:
                    funciones_definidas.add(match_def.group(2))
                    continue

            linea_sin_strings = limpiar_strings(linea)
            for match in patron_llamada_func.findall(linea_sin_strings):
                if match in palabras_clave:
                    continue
                llamadas.append((line_num, match))

    todas_las_funciones = funciones_definidas | funciones_builtin

    for line_num, nombre in llamadas:
        if nombre not in todas_las_funciones:
            sugerencias = get_close_matches(nombre, todas_las_funciones, n=1)
            if sugerencias:
                errores.append(
                    f"[Línea {line_num}] Error: La función '{nombre}' no está definida. ¿Quiso decir '{sugerencias[0]}'?"
                )
            else:
                errores.append(
                    f"[Línea {line_num}] Error: La función '{nombre}' fue llamada pero no está definida o no ha sido declarada."
                )

    return errores



def validar_punto_y_coma(input_file):
    with open(input_file, "r") as file:
        lines = file.readlines()

    errores = []
    for i, line in enumerate(lines):
        original_line = line.strip()
        if not original_line or original_line.startswith("#"):
            continue

        sin_comentario = original_line.split("#", 1)[0].strip()
        line_lower = sin_comentario.lower()

        if line_lower.startswith("} loop") and not sin_comentario.endswith(";"):
            errores.append(f"[Línea {i + 1}] Error: Se esperaba ';' al final del bloque 'loop'. Instrucción: {original_line}")
            continue

        estructuras_sin_punto_y_coma = (
            line_lower.startswith(("program", "ini", "end", "funs", "si", "no", "for", "loop", "do"))
            or line_lower.endswith("{")
            or line_lower in ("{", "}", "fin")
        )
        if estructuras_sin_punto_y_coma:
            continue

        if "(" in line_lower and ")" in line_lower and not sin_comentario.endswith(";"):
            errores.append(f"[Línea {i + 1}] Error: Posible llamada o retorno sin ';'. Instrucción: {original_line}")
            continue

        if not sin_comentario.endswith(";"):
            errores.append(f"[Línea {i + 1}] Error: Falta ';' al final de la instrucción. Línea: {original_line}")

    return errores

def validar_parentesis(input_file):
    with open(input_file, "r") as file:
        lines = file.readlines()

    errores = []
    stack = []

    for num_linea, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        in_string = False
        for idx, char in enumerate(line):
            if char == '"':
                in_string = not in_string
            elif char == '(' and not in_string:
                stack.append((num_linea, idx + 1))
            elif char == ')' and not in_string:
                if not stack:
                    errores.append(f"[Línea {num_linea}, Columna {idx + 1}] Error: Paréntesis de cierre ')' sin apertura correspondiente.")
                else:
                    stack.pop()

    for linea, columna in stack:
        errores.append(f"[Línea {linea}, Columna {columna}] Error: Paréntesis de apertura '(' sin cierre correspondiente.")

    return errores

def validar_llaves(input_file):
    with open(input_file, "r") as file:
        lines = file.readlines()

    errores = []
    stack = []

    for num_linea, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        in_string = False
        for idx, char in enumerate(line):
            if char == '"':
                in_string = not in_string
            elif char == '{' and not in_string:
                stack.append((num_linea, idx + 1))
            elif char == '}' and not in_string:
                if not stack:
                    errores.append(f"[Línea {num_linea}, Columna {idx + 1}] Error: Llave de cierre '}}' sin apertura correspondiente.")
                else:
                    stack.pop()

    for linea, columna in stack:
        errores.append(f"[Línea {linea}, Columna {columna}] Error: Llave de apertura '{{' sin cierre correspondiente.")

    return errores

def validar_nombres_variables(input_file):
    palabras_reservadas = {
        'program', 'ini', 'end', 'si', 'no', 'for', 'loop', 'do', 'ret', 'mst',
        'int', 'flt', 'bool', 'str', 'aut', 'vd', 'funs', 'void'
    }

    tipos_validos = {'int', 'flt', 'bool', 'str', 'aut', 'vd', 'void'}
    patron_variable = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    errores = []

    with open(input_file, 'r') as file:
        for line_num, line in enumerate(file, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            line_lower = line.lower()
            if (
                line.endswith("{") or
                line == "{" or line == "}" or
                any(line_lower.startswith(kw) for kw in {'program', 'ini', 'end', 'funs', 'ret', 'mostrar'})
            ):
                continue

            if '=' in line:
                izquierda = line.split('=')[0].strip()
                partes = izquierda.split()
            else:
                partes = line.split()

            if not partes:
                continue

            tipo = partes[0].lower()
            if tipo not in tipos_validos:
                continue

            if len(partes) < 2:
                errores.append(f"[Línea {line_num}] Error: Se esperaba un nombre de variable después del tipo '{tipo}'.")
                continue

            nombre_var = partes[1]
            if not patron_variable.match(nombre_var):
                errores.append(f"[Línea {line_num}] Error: El nombre de variable '{nombre_var}' no es válido. Debe comenzar con letra o '_' y contener solo letras, números o '_'.")
            elif nombre_var.lower() in palabras_reservadas:
                errores.append(f"[Línea {line_num}] Error: El nombre '{nombre_var}' es una palabra reservada y no puede usarse como identificador.")

    return errores

def validar_tipos_invalidos(input_file):
    errores = []
    tipos_validos = {'int',
                      'flt', 'bol', 'str', 'aut', 'vd', 'void'}
    patron_tipo = re.compile(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+[a-zA-Z_][a-zA-Z0-9_]*\s*(=.*)?;')

    with open(input_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            linea = line.strip()
            if not linea or linea.startswith("#"):
                continue

            match = patron_tipo.match(linea)
            if match:
                tipo = match.group(1).lower()
                if tipo not in tipos_validos:
                    errores.append(f"[Línea {line_num}] Error: Tipo de dato inválido '{match.group(1)}'. ¿Quiso decir 'int', 'flt', 'bol', etc.?")

    return errores


def validar_len_sintaxis_general(ruta_archivo):
    errores = []
    errores += validar_punto_y_coma(ruta_archivo)
    errores += validar_parentesis(ruta_archivo)
    errores += validar_llaves(ruta_archivo)
    errores += validar_nombres_variables(ruta_archivo)
    errores += validar_llamadas_invalidas(ruta_archivo)
    errores += sugerir_palabras_clave_invalidas(ruta_archivo)
    errores += validar_parentesis_vacios(ruta_archivo)
    return errores