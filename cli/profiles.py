import os
import sys
from cli.utils import limpiar_pantalla, cargar_json, preguntar_archivo, guardar_json, preguntar_si_no
from cli.wizard import inicializar_archivos_perfil, asistente_mapeo_columnas

DIRECTORIO_PERFILES = "profiles"

def seleccionar_perfil(perfil_actual, inicio=False):
    while True:
        limpiar_pantalla()
        print("--- 👤 SELECCIÓN DE PERFIL ---")
        if perfil_actual:
            print(f"Perfil actual: [{perfil_actual}]\n")
        else:
            print("👋 ¡Bienvenido! Necesitás seleccionar o crear un perfil para empezar.\n")
        
        os.makedirs(DIRECTORIO_PERFILES, exist_ok=True)
        carpetas_perfiles = [d for d in os.listdir(DIRECTORIO_PERFILES) if os.path.isdir(os.path.join(DIRECTORIO_PERFILES, d))]
        
        if not carpetas_perfiles:
            print("⚠️ No se encontraron perfiles. Por favor, creá uno nuevo.")
            
        print("Perfiles disponibles:")
        for i, carpeta in enumerate(carpetas_perfiles, 1):
            ruta_info = os.path.join(DIRECTORIO_PERFILES, carpeta, "profile.json")
            nombre_mostrar, descripcion = carpeta, ""
            
            if os.path.exists(ruta_info):
                info = cargar_json(ruta_info)
                if info:
                    nombre_mostrar = info.get("name", carpeta)
                    desc = info.get("description", "")
                    descripcion = f" - {desc}" if desc else ""
            
            marcador = " 🟢 (Activo)" if carpeta == perfil_actual else ""
            print(f"  [{i}] {nombre_mostrar}{descripcion}{marcador} (Dir: {carpeta})")
            
        print("\nAcciones:")
        print("  [N] Crear nuevo perfil")
        if not inicio or perfil_actual:
            print("  [0] Volver al menú principal")
        elif inicio and not carpetas_perfiles:
            print("  [S] Salir del programa")
            
        opcion = input("\nElegí una opción: ").strip().upper()
        
        if opcion == '0' and (not inicio or perfil_actual):
            return perfil_actual
        elif opcion == 'S' and inicio and not carpetas_perfiles:
            sys.exit(0)
        elif opcion == 'N':
            nuevo_dir = input("Ingresá el nombre de la carpeta para el nuevo perfil (ej: mi_empresa): ").strip().lower().replace(" ", "_")
            if nuevo_dir:
                ruta_nuevo = os.path.join(DIRECTORIO_PERFILES, nuevo_dir)
                ruta_configs = os.path.join(ruta_nuevo, "configs")
                os.makedirs(ruta_configs, exist_ok=True)
                
                print("\n--- 🛠️  SETUP WIZARD ---")
                nombre_perfil = input("Nombre a mostrar del perfil: ").strip() or nuevo_dir
                desc_perfil = input("Descripción del perfil: ").strip() or "Nuevo perfil"
                
                print("\n(Opcional) Proveer archivos de muestra acelera la configuración automática.")
                archivo_stock = preguntar_archivo("Ruta del archivo de Stock de ejemplo", "")
                archivo_sistema = preguntar_archivo("Ruta del archivo de Sistema (Cruces) de ejemplo", "")
                
                guardar_json(os.path.join(ruta_nuevo, "profile.json"), {
                    "name": nombre_perfil,
                    "description": desc_perfil,
                    "version": "1.0",
                    "sample_files": {
                        "stock": archivo_stock,
                        "sistema": archivo_sistema
                    }
                })
                
                inicializar_archivos_perfil(ruta_configs)
                perfil_actual = nuevo_dir
                print(f"\n✅ Perfil '{nombre_perfil}' creado e inicializado exitosamente.")
                
                if archivo_stock and os.path.exists(archivo_stock):
                    if preguntar_si_no("¿Querés que analicemos el archivo de Stock para autoconfigurar las columnas?"):
                        asistente_mapeo_columnas(archivo_stock, ruta_nuevo)
                
                if preguntar_si_no("¿Querés configurar el resto de los parámetros manualmente ahora mismo?"):
                    from cli.config_menu import menu_configuracion
                    menu_configuracion(perfil_actual)
                
                if inicio:
                    return perfil_actual
        elif opcion.isdigit() and 1 <= int(opcion) <= len(carpetas_perfiles):
            perfil_actual = carpetas_perfiles[int(opcion) - 1]
            print(f"✅ Perfil cambiado exitosamente a '{perfil_actual}'.")
            input("Presioná Enter para continuar...")
            if inicio:
                return perfil_actual
        else:
            print("❌ Opción inválida.")
            input("Presioná Enter para continuar...")