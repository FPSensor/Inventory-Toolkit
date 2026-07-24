from argparse import Namespace
from cli.utils import limpiar_pantalla, preguntar_archivo, validar_archivos_existen

def ejecutar_cruce(perfil_actual):
    limpiar_pantalla()
    print(f"--- 🔄 INICIANDO CRUCE DE INVENTARIO (Perfil: {perfil_actual}) ---\n")
    
    archivo_sistema = preguntar_archivo("1. Archivo de stock (Sistema)", "Sistema.xls")
    archivo_conteo = preguntar_archivo("2. Archivo de Conteo Físico", "Conteo.xlsx")
    costo = preguntar_archivo("3. Archivo de Costo", "Costo.xlsx")
    venta = preguntar_archivo("4. Archivo de Venta", "Venta.xlsx")
    
    if not validar_archivos_existen([archivo_sistema, archivo_conteo, costo, venta]):
        print("\n⚠️ Operación abortada. Faltan archivos necesarios.")
        input("Presioná Enter para volver al menú...")
        return

    out = preguntar_archivo("\n5. Nombre del archivo resultante", "Cruce_Resultados.xlsx", es_salida=True)
    if not out.endswith(('.xlsx', '.xls')):
        out += ".xlsx"

    # --- NUEVO: Preguntas interactivas para las banderas lógicas ---
    print("\n--- ⚙️ Opciones de Cruce ---")
    resp_ds = input("¿Consolidar cantidades de múltiples bases? (S/N) [N]: ").strip().upper()
    flag_ds = True if resp_ds == 'S' else False

    resp_parcial = input("¿Filtrar stock sólo por artículos escaneados (Cruce Parcial)? (S/N) [N]: ").strip().upper()
    flag_parcial = True if resp_parcial == 'S' else False

    print(f"\n🚀 Cruzando datos... (Output: {out})")
    
    # Construcción del Namespace corregida
    args = Namespace(
        sistema=archivo_sistema, # CORREGIDO: antes decía 'input'
        conteo=archivo_conteo, 
        costo=costo, 
        venta=venta, 
        out=out, 
        profile=perfil_actual,
        ds=flag_ds,              # CORREGIDO: ahora toma tu respuesta
        parcial=flag_parcial     # CORREGIDO: ahora toma tu respuesta
    )
    
    try:
        from engine import Cruces # Asumiendo que el archivo se llama Cruces.py en minúscula
        Cruces.ejecutar_cruce(args) # CORREGIDO: llamado a la función correcta
        # NOTA: Quité el print de éxito de acá, porque el motor de cruces ya tiene su propio print de éxito al final.
    except ImportError as e:
        print(f"\n❌ No se puede ejecutar: Faltan módulos ({e}).")
    except Exception as e:
        print(f"\n❌ Error crítico: {e}")
        
    input("\nPresioná Enter para volver al menú...")