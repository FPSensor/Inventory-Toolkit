import os
from cli.utils import cargar_json, guardar_json, limpiar_pantalla, preguntar_archivo, abrir_en_editor
from cli.wizard import PANDAS_DISPONIBLE

try:
    import pandas as pd
except ImportError:
    pass

DIRECTORIO_PERFILES = "profiles"

def gestionar_diccionario_de_listas(ruta_json, titulo, perfil_actual):
    datos = cargar_json(ruta_json)
    if datos is None:
        input("Presioná Enter para volver...")
        return

    while True:
        limpiar_pantalla()
        print(f"--- 🛠️  CONFIGURACIÓN: {titulo} ---")
        print(f"Perfil: {perfil_actual} | Archivo: {os.path.basename(ruta_json)}\n")
        
        categorias = sorted(datos.keys())
        for i, cat in enumerate(categorias, 1):
            print(f"[{i}] {cat}")
        print("[0] Volver al menú anterior")
        print("[+] Crear nueva categoría")
        
        opcion_cat = input("\nSeleccioná una opción: ").strip()
        
        if opcion_cat == '0':
            break
        elif opcion_cat == '+':
            nueva_cat = input("Nombre de la nueva categoría: ").strip()
            if nueva_cat:
                datos[nueva_cat] = []
                guardar_json(ruta_json, datos)
            continue
            
        if not opcion_cat.isdigit() or not (1 <= int(opcion_cat) <= len(categorias)):
            print("❌ Opción inválida.")
            input("Presioná Enter para intentar de nuevo...")
            continue

        categoria_actual = categorias[int(opcion_cat) - 1]
        
        while True:
            limpiar_pantalla()
            print(f"--- Editando: {categoria_actual.upper()} ---")
            
            items = datos[categoria_actual]
            if not isinstance(items, list):
                print("⚠️  Esta categoría no contiene una lista editable. Volviendo...")
                input("Presioná Enter...")
                break

            if not items:
                print("  (Lista vacía)")
            else:
                for i, item in enumerate(items, 1):
                    print(f"  {i}. {item}")
            
            print("\nAcciones:")
            print("[A] Agregar manual")
            
            es_categoria_columnas = "columna" in categoria_actual.lower()
            if PANDAS_DISPONIBLE and es_categoria_columnas:
                print("[X] 📊 Extraer desde un archivo Excel")
                
            if items:
                print("[C] Corregir un ítem")
                print("[E] Eliminar un ítem")
            print("[V] Volver a las categorías")
            
            accion = input("\nElegí una acción: ").strip().upper()
            
            if accion == 'V':
                break
            elif accion == 'A':
                nuevo_item = input("Ingresá el nuevo valor: ").strip()
                if nuevo_item:
                    datos[categoria_actual].append(nuevo_item)
                    guardar_json(ruta_json, datos)
                    
            elif accion == 'X' and PANDAS_DISPONIBLE and es_categoria_columnas:
                print("\n🔍 Buscando archivo para extraer columnas...")
                ruta = preguntar_archivo("Ruta del archivo Excel", "")
                
                if ruta and os.path.exists(ruta):
                    try:
                        df_temp = pd.read_excel(ruta, nrows=0)
                        cols = list(df_temp.columns)
                        
                        print(f"\n--- Columnas en {os.path.basename(ruta)} ---")
                        for i_col, nom_col in enumerate(cols, 1):
                            marca = " ✓ (Ya en tu lista)" if nom_col in datos[categoria_actual] else ""
                            print(f"  [{i_col}] {nom_col}{marca}")
                            
                        print("\n💡 Podés ingresar varios números separados por coma (ej: 1,3,4)")
                        print("  [0] Cancelar")
                        seleccion = input("Seleccioná las columnas a agregar: ").strip()
                        
                        if seleccion != '0':
                            agregados = 0
                            for num_str in seleccion.split(','):
                                if num_str.strip().isdigit():
                                    idx = int(num_str.strip())
                                    if 1 <= idx <= len(cols):
                                        col_elegida = cols[idx - 1]
                                        if col_elegida not in datos[categoria_actual]:
                                            datos[categoria_actual].append(col_elegida)
                                            agregados += 1
                            
                            if agregados > 0:
                                print(f"✅ Se agregaron {agregados} columnas exitosamente.")
                                guardar_json(ruta_json, datos)
                            else:
                                print("⚠️ No se agregaron columnas (ya estaban en la lista o la selección fue inválida).")
                            input("Presioná Enter para continuar...")
                            
                    except Exception as e:
                        print(f"❌ Error al leer el archivo: {e}")
                        input("Presioná Enter...")
                else:
                    print("⚠️ Archivo no encontrado o cancelado.")
                    input("Presioná Enter...")
                    
            elif accion == 'E' and items:
                idx = input("Ingresá el NÚMERO del ítem a eliminar: ").strip()
                if idx.isdigit() and 1 <= int(idx) <= len(items):
                    item_eliminado = datos[categoria_actual].pop(int(idx) - 1)
                    print(f"🗑️ Se eliminó: '{item_eliminado}'")
                    guardar_json(ruta_json, datos)
                    input("Presioná Enter...")
            elif accion == 'C' and items:
                idx = input("Ingresá el NÚMERO del ítem a corregir: ").strip()
                if idx.isdigit() and 1 <= int(idx) <= len(items):
                    viejo_valor = datos[categoria_actual][int(idx) - 1]
                    nuevo_valor = input(f"Nuevo valor para '{viejo_valor}': ").strip()
                    if nuevo_valor:
                        datos[categoria_actual][int(idx) - 1] = nuevo_valor
                        guardar_json(ruta_json, datos)

def gestionar_diccionario_simple(ruta_json, titulo, perfil_actual):
    datos = cargar_json(ruta_json)
    if datos is None:
        input("Presioná Enter para volver...")
        return

    while True:
        limpiar_pantalla()
        print(f"--- 🛠️  CONFIGURACIÓN: {titulo} ---")
        print(f"Perfil: {perfil_actual} | Archivo: {os.path.basename(ruta_json)}\n")
        
        claves = sorted(datos.keys())
        for i, k in enumerate(claves, 1):
            print(f"[{i}] {k}: {datos[k]}")
        
        print("\nAcciones:")
        print("  [#] Número para editar un valor existente")
        print("  [A] Agregar nueva clave-valor")
        print("  [E] Eliminar una clave")
        print("  [0] Volver al menú anterior")
        
        opcion = input("\nElegí una acción: ").strip().upper()
        
        if opcion == '0':
            break
        elif opcion == 'A':
            nueva_clave = input("Ingresá el nombre de la nueva clave: ").strip()
            if nueva_clave:
                nuevo_valor = input(f"Ingresá el valor para '{nueva_clave}': ").strip()
                if nuevo_valor.lower() == 'true': nuevo_valor = True
                elif nuevo_valor.lower() == 'false': nuevo_valor = False
                elif nuevo_valor.isdigit(): nuevo_valor = int(nuevo_valor)
                datos[nueva_clave] = nuevo_valor
                guardar_json(ruta_json, datos)
        elif opcion == 'E':
            idx = input("Número del ítem a eliminar: ").strip()
            if idx.isdigit() and 1 <= int(idx) <= len(claves):
                clave_a_borrar = claves[int(idx) - 1]
                del datos[clave_a_borrar]
                print(f"🗑️ Eliminado: {clave_a_borrar}")
                guardar_json(ruta_json, datos)
                input("Presioná Enter...")
        elif opcion.isdigit() and 1 <= int(opcion) <= len(claves):
            clave_actual = claves[int(opcion) - 1]
            valor_actual = datos[clave_actual]
            print(f"\nEditando [{clave_actual}]. Valor actual: {valor_actual}")
            nuevo_valor = input("Ingresá el nuevo valor (dejá en blanco para cancelar): ").strip()
            
            if nuevo_valor:
                if isinstance(valor_actual, bool):
                    datos[clave_actual] = nuevo_valor.lower() in ('true', '1', 'si', 's', 'yes')
                elif isinstance(valor_actual, int) and nuevo_valor.isdigit():
                    datos[clave_actual] = int(nuevo_valor)
                else:
                    datos[clave_actual] = nuevo_valor
                guardar_json(ruta_json, datos)

def menu_configuracion(perfil_actual):
    archivos_config = {
        '1': {'archivo': 'familias.json', 'tipo': 'listas', 'titulo': 'Familias de Productos'},
        '2': {'archivo': 'cleaning.json', 'tipo': 'listas', 'titulo': 'Reglas de Limpieza'},
        '3': {'archivo': 'exclusions.json', 'tipo': 'listas', 'titulo': 'Exclusiones'},
        '4': {'archivo': 'settings.json', 'tipo': 'simple', 'titulo': 'Ajustes Generales'},
        '5': {'archivo': 'databases.json', 'tipo': 'simple', 'titulo': 'Mapeo de Bases de Datos'},
        '6': {'archivo': 'reports.json', 'tipo': 'complejo', 'titulo': 'Estructura de Reportes'},
        '7': {'archivo': 'stores.json', 'tipo': 'complejo', 'titulo': 'Locales y Regiones'},
        '8': {'archivo': 'schema.json', 'tipo': 'complejo', 'titulo': 'Esquema de Validación'}
    }

    while True:
        limpiar_pantalla()
        print(f"--- ⚙️  CENTRAL DE CONFIGURACIÓN (Perfil: {perfil_actual}) ---")
        print("\n📝 LISTAS DE DATOS (Interactivo)")
        print("  [1] Familias (familias.json)")
        print("  [2] Limpieza de Columnas (cleaning.json)")
        print("  [3] Exclusiones (exclusions.json)")
        
        print("\n🔧 AJUSTES BÁSICOS (Interactivo)")
        print("  [4] Ajustes Generales (settings.json)")
        print("  [5] Bases de Datos (databases.json)")
        
        print("\n🧠 ESTRUCTURAS COMPLEJAS (Abre en editor externo)")
        print("  [6] Reportes (reports.json)")
        print("  [7] Locales (stores.json)")
        print("  [8] Esquema Lógico (schema.json)")
        
        print("\n  [0] ↩️  Volver al menú principal")
        
        opcion = input("\nElegí un archivo para configurar: ").strip()
        
        if opcion == '0':
            break
            
        if opcion in archivos_config:
            config_seleccionada = archivos_config[opcion]
            ruta_configs = os.path.join(DIRECTORIO_PERFILES, perfil_actual, "configs")
            ruta_archivo = os.path.join(ruta_configs, config_seleccionada['archivo'])
            
            if config_seleccionada['tipo'] == 'listas':
                gestionar_diccionario_de_listas(ruta_archivo, config_seleccionada['titulo'], perfil_actual)
            elif config_seleccionada['tipo'] == 'simple':
                gestionar_diccionario_simple(ruta_archivo, config_seleccionada['titulo'], perfil_actual)
            elif config_seleccionada['tipo'] == 'complejo':
                abrir_en_editor(ruta_archivo)
        else:
            print("❌ Opción inválida.")
            input("Presioná Enter para continuar...")