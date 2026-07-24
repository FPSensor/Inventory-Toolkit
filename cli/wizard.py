import os
from cli.utils import guardar_json, cargar_json, preguntar_si_no

try:
    import pandas as pd
    PANDAS_DISPONIBLE = True
except ImportError:
    PANDAS_DISPONIBLE = False

def inicializar_archivos_perfil(ruta_configs):
    """Genera la estructura base de los archivos JSON para un perfil nuevo."""
    plantillas = {
        "familias.json": {},
        "cleaning.json": {"columnas_texto_a_limpiar": [], "columnas_a_eliminar": [], "columnas_a_formatear": []},
        "exclusions.json": {"excluded_articles": [], "excluded_keywords": []},
        "settings.json": {"columna_articulo": "Artículo", "columna_familia": "Familias", "calcular_diferencias": True},
        "databases.json": {},
        "reports.json": {"orden_columnas_base": [], "resumenes": []},
        "stores.json": {"locales_activos": [], "grupos_regionales": {}},
        "schema.json": {}
    }
    
    for archivo, estructura in plantillas.items():
        ruta = os.path.join(ruta_configs, archivo)
        if not os.path.exists(ruta):
            guardar_json(ruta, estructura)

def asistente_mapeo_columnas(ruta_archivo, perfil_dir):
    """Lee los encabezados de un archivo y asiste al usuario para mapear columnas."""
    if not PANDAS_DISPONIBLE or not os.path.exists(ruta_archivo):
        return

    print(f"\n--- 🧠 ANALIZANDO ESTRUCTURA: {os.path.basename(ruta_archivo)} ---")
    try:
        df = pd.read_excel(ruta_archivo, nrows=0)
        columnas_reales = list(df.columns)
    except Exception as e:
        print(f"❌ No se pudo leer el archivo para auto-mapeo: {e}")
        return

    print("Columnas detectadas en el archivo:")
    for i, col in enumerate(columnas_reales, 1):
        print(f"  [{i}] {col}")
    print("-" * 40)

    mapeos_necesarios = {
        "columna_articulo": {
            "descripcion": "Artículo / Código de Producto",
            "candidatos": ["Artículo", "Articulo", "Cod", "Codigo", "SKU", "Art"]
        },
        "columna_familia": {
            "descripcion": "Familia / Categoría",
            "candidatos": ["Familia", "Familias", "Rubro", "Categoria", "Línea"]
        }
    }

    ruta_settings = os.path.join(perfil_dir, "configs", "settings.json")
    settings_actuales = cargar_json(ruta_settings) or {}

    for clave_config, datos_mapeo in mapeos_necesarios.items():
        columna_sugerida = None
        
        for candidato in datos_mapeo["candidatos"]:
            coincidencias = [c for c in columnas_reales if candidato.lower() in str(c).lower()]
            if coincidencias:
                columna_sugerida = coincidencias[0]
                break
        
        if columna_sugerida:
            print(f"\n💡 Creemos que la columna para '{datos_mapeo['descripcion']}' es: [{columna_sugerida}]")
            es_correcto = preguntar_si_no("¿Es esto cierto?")
            
            if es_correcto:
                settings_actuales[clave_config] = str(columna_sugerida)
                print(f"✅ Mapeo guardado: {clave_config} = {columna_sugerida}")
                continue
                
        print(f"\n¿A qué columna hace referencia '{datos_mapeo['descripcion']}'?")
        for i, col in enumerate(columnas_reales, 1):
            print(f"  [{i}] {col}")
        print("  [0] Omitir configuración por ahora")
        
        while True:
            seleccion = input("Seleccioná el número correspondiente: ").strip()
            if seleccion == '0':
                break
            elif seleccion.isdigit() and 1 <= int(seleccion) <= len(columnas_reales):
                columna_elegida = str(columnas_reales[int(seleccion) - 1])
                settings_actuales[clave_config] = columna_elegida
                print(f"✅ Mapeo manual guardado: {clave_config} = {columna_elegida}")
                break
            else:
                print("❌ Selección inválida.")

    guardar_json(ruta_settings, settings_actuales)
    print("\n✅ Análisis y mapeo de archivo finalizado.")
    input("Presioná Enter para continuar...")