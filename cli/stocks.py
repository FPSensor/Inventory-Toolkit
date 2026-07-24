from argparse import Namespace
from cli.utils import limpiar_pantalla, preguntar_archivo, validar_archivos_existen

def ejecutar_stock(perfil_actual):
    limpiar_pantalla()
    print(f"--- 📦 INICIANDO PROCESAMIENTO DE STOCK (Perfil: {perfil_actual}) ---\n")
    
    stock = preguntar_archivo("1. Archivo de Stock", "Stock.xlsx")
    costo = preguntar_archivo("2. Archivo de Costo", "Costo.xlsx")
    venta = preguntar_archivo("3. Archivo de Venta", "Venta.xlsx")
    
    if not validar_archivos_existen([stock, costo, venta]):
        print("\n⚠️ Operación abortada. Faltan archivos necesarios.")
        input("Presioná Enter para volver al menú...")
        return

    out = preguntar_archivo("\n4. Nombre del archivo resultante", "Stock_Final.xlsx", es_salida=True)
    if not out.endswith(('.xlsx', '.xls')):
        out += ".xlsx"

    print(f"\n🚀 Procesando inventario... (Output: {out})")
    
    args = Namespace(stock=stock, costo=costo, venta=venta, out=out, profile=perfil_actual)
    
    try:
        from engine import Stocks
        Stocks.procesar_stock(args)
        print("\n✅ ¡Procesamiento finalizado exitosamente!")
    except ImportError:
        print("\n❌ No se puede ejecutar: Faltan módulos en 'engine/'.")
    except Exception as e:
        print(f"\n❌ Error crítico: {e}")
        
    input("\nPresioná Enter para volver al menú...")