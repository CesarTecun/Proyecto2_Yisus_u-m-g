import os
import subprocess
import time
from antlr4 import FileStream, CommonTokenStream, ParseTreeWalker
from LenLexer import LenLexer
from LenParser import LenParser
from creador_ast import ASTBuilder
from generador_len import LLVMGeneratorLen
from SemanticoVal import SemanticListener, SemanticError
from SintacticoVal import validar_len_sintaxis_general

def listar_archivos_txt(directorio="."):
    return [f for f in os.listdir(directorio) if f.endswith(".txt")]

def ejecutar_ll_con_lli(nombre_archivo_ll):
    print("\n[INFO] Ejecutando IR con `lli`...")
    try:
        inicio = time.perf_counter()
        
        # ✅ Ejecutar directamente sin capturar para ver salida en tiempo real
        subprocess.run(["lli", nombre_archivo_ll])
        
        fin = time.perf_counter()
        print(f"[INFO] Tiempo de ejecución: {fin - inicio:.4f} segundos")

    except FileNotFoundError:
        print("✖ Error: No se encontró `lli`. Asegúrate de tener LLVM instalado y `lli` disponible en PATH.")
    except Exception as e:
        print(f"✖ Error al ejecutar: {e}")


def encontrar_funciones(tree):
    from LenParser import LenParser
    for i in range(tree.getChildCount()):
        hijo = tree.getChild(i)
        if isinstance(hijo, LenParser.FuncionesContext):
            return hijo
        if hasattr(hijo, 'getChildCount') and hijo.getChildCount() > 0:
            resultado = encontrar_funciones(hijo)
            if resultado:
                return resultado
    return None

def compilar_archivo(ruta, optimizar=False):
    tiempos = {}
    tiempo_total_inicio = time.perf_counter()  # Inicio total

    # Fase 1: Validación sintáctica
    tiempo_ini = time.perf_counter()
    errores_sintacticos = validar_len_sintaxis_general(ruta)
    if errores_sintacticos:
        print("✖ Errores sintácticos encontrados:")
        for err in errores_sintacticos:
            print(err)
        return None
    print("✔ Validación sintáctica completada.")
    tiempos['Sintáctico'] = time.perf_counter() - tiempo_ini

    # Fase 2: Lexer + Parser
    tiempo_ini = time.perf_counter()
    input_stream = FileStream(ruta, encoding='utf-8')
    lexer = LenLexer(input_stream)
    tokens = CommonTokenStream(lexer)
    parser = LenParser(tokens)
    tree = parser.prog()
    tiempos['Lexer/Parser'] = time.perf_counter() - tiempo_ini

    # Fase 3: Semántico
    print("👀 Validando semánticamente...")
    tiempo_ini = time.perf_counter()
    walker = ParseTreeWalker()
    sem_listener = SemanticListener()
    funciones_node = encontrar_funciones(tree)
    if funciones_node:
        sem_listener.pre_register_functions(funciones_node)
    walker.walk(sem_listener, tree)
    print("✔ Validación semántica completada.")
    tiempos['Semántico'] = time.perf_counter() - tiempo_ini

    # Fase 4: AST
    tiempo_ini = time.perf_counter()
    builder = ASTBuilder()
    ast = builder.visit(tree)
    print("✔ AST construido correctamente")
    tiempos['AST'] = time.perf_counter() - tiempo_ini

    # Fase 5: LLVM IR
    tiempo_ini = time.perf_counter()
    generator = LLVMGeneratorLen()
    llvm_module = generator.generate(ast)
    print("✔ LLVM IR generado correctamente")
    tiempos['LLVM Gen'] = time.perf_counter() - tiempo_ini

    # Fase 6: Escritura .ll
    tiempo_ini = time.perf_counter()
    nombre_base = os.path.splitext(ruta)[0]
    archivo_salida = f"{nombre_base}.ll"
    with open(archivo_salida, "w", encoding="ascii", newline="\n") as f:
        f.write(str(generator.module))
        f.flush()
        os.fsync(f.fileno())
    print(f"✔ Archivo guardado como '{archivo_salida}'")
    tiempos['Escritura .ll'] = time.perf_counter() - tiempo_ini

    # Fase 7: Optimización (si aplica)
    if optimizar:
        tiempo_ini = time.perf_counter()
        archivo_opt = f"{nombre_base}_opt.ll"
        resultado = subprocess.run(
            ["opt", "-O2", archivo_salida, "-S", "-o", archivo_opt],
            capture_output=True, text=True
        )
        if resultado.returncode != 0:
            print("✖ Error al optimizar con `opt`:")
            print(resultado.stderr)
            return None
        print(f"✔ Archivo optimizado guardado como '{archivo_opt}'")
        tiempos['Optimización'] = time.perf_counter() - tiempo_ini

        # Fase 8: Ejecución IR optimizado
        tiempo_ini = time.perf_counter()
        ejecutar_ll_con_lli(archivo_opt)
        tiempos['Ejecución IR'] = time.perf_counter() - tiempo_ini
    else:
        # Fase 8: Ejecución IR sin optimizar
        tiempo_ini = time.perf_counter()
        ejecutar_ll_con_lli(archivo_salida)
        tiempos['Ejecución IR'] = time.perf_counter() - tiempo_ini

    # Tiempo total
    tiempo_total_fin = time.perf_counter()
    tiempos['TOTAL'] = tiempo_total_fin - tiempo_total_inicio

    # Reporte final
    print("\n=== TIEMPOS DE FASES ===")
    for fase, duracion in tiempos.items():
        print(f"{fase:15}: {duracion:.4f} seg")

    return archivo_salida



def generar_exe_desde_ll():
    archivos_ll = [f for f in os.listdir() if f.endswith(".ll")]
    if not archivos_ll:
        print("✖ No hay archivos .ll disponibles en el directorio actual.")
        return

    print("\n== Archivos .ll disponibles ==")
    for idx, archivo in enumerate(archivos_ll, 1):
        print(f"{idx}. {archivo}")

    try:
        seleccion = int(input("Seleccione el archivo a compilar (número): "))
        if not 1 <= seleccion <= len(archivos_ll):
            print("✖ Selección inválida.")
            return
        input_ll = archivos_ll[seleccion - 1]
    except ValueError:
        print("✖ Entrada no válida.")
        return

    output_base = os.path.splitext(input_ll)[0]
    output_obj = output_base + ".o"
    output_exe = output_base + ".exe"

    print("[INFO] Generando archivo objeto con llc...")
    result_llc = subprocess.run(
        ["llc", "-mtriple=x86_64-pc-windows-gnu", "-filetype=obj", input_ll, "-o", output_obj],
        capture_output=True, text=True
    )
    if result_llc.returncode != 0:
        print("[ERROR] Falló la compilación con llc:")
        print(result_llc.stderr)
        return

    print("[INFO] Enlazando con x86_64-w64-mingw32-gcc...")
    result_gcc = subprocess.run([
        "x86_64-w64-mingw32-gcc", output_obj, "-o", output_exe
    ], capture_output=True, text=True)
    if result_gcc.returncode != 0:
        print("[ERROR] Falló el enlace con mingw-w64:")
        print(result_gcc.stderr)
        return

    print(f"[OK] Ejecutable generado: {output_exe}")


def main():
    while True:
        print("\n=== MENÚ COMPILADOR LEN ===")
        print("1. Ejecutar sin optimizar")
        print("2. Ejecutar con optimización -O2")
        print("3. Ejecutar .ll optimizado manualmente")
        print("4. Generar .exe para Windows")
        print("5. Salir")

        opcion = input("Seleccione una opción: ").strip()

        if opcion in {"1", "2"}:
            archivos = listar_archivos_txt()
            if not archivos:
                print("✖ No hay archivos .txt disponibles.")
                continue
            for idx, a in enumerate(archivos, 1):
                print(f"{idx}. {a}")
            idx = int(input("Seleccione archivo a compilar: "))
            if not 1 <= idx <= len(archivos):
                print("Opcion inválida.")
                continue
            ruta = archivos[idx - 1]
            compilar_archivo(ruta, optimizar=(opcion == "2"))

        elif opcion == "3":
            ll_file = input("Ingrese nombre de archivo .ll manual: ").strip()
            if not ll_file.endswith(".ll"):
                ll_file += ".ll"
            if os.path.exists(ll_file):
                ejecutar_ll_con_lli(ll_file)
            else:
                print("✖ Archivo no encontrado.")

        elif opcion == "4":
            generar_exe_desde_ll()

        elif opcion == "5":
            print("Saliendo del compilador.")
            break

        else:
            print("✖ Opción no válida.")

if __name__ == "__main__":
    main()