import sys
from cli.utils import limpiar_pantalla
from cli.profiles import seleccionar_perfil
from cli.config_menu import menu_configuracion
from cli.cruces import ejecutar_cruce
from cli.stocks import ejecutar_stock
from cli.reports import menu_reports
from cli.wizard import PANDAS_DISPONIBLE

try:
    from engine import Stocks
    from engine import Cruces
    MODULOS_CARGADOS = True
except ImportError as e:
    MODULOS_CARGADOS = False
    error_msg = e

def main():
    if not PANDAS_DISPONIBLE:
        print("⚠️ Advertencia: Pandas no está instalado.")
    
    if not MODULOS_CARGADOS:
        print(f"⚠️ Advertencia: No se pudieron cargar los módulos base ({error_msg}).")
        input("Presioná Enter para iniciar el menú en modo degradado...")

    perfil_actual = seleccionar_perfil(None, inicio=True)
    
    try:
        while True:
            limpiar_pantalla()
            print("========================================")
            print("       INVENTORY TOOLKIT v1.3.0 CLI       ")
            print(f"       Perfil Activo: [{perfil_actual}]  ")
            print("========================================")
            print("¿Qué querés hacer hoy?\n")
            print("  [C] 🔄 Cruce de Inventario")
            print("  [S] 📦 Procesamiento de Stock")
            print("  [R] 📊 Generate YoY Sales Report")
            print("  [K] ⚙️ Configuraciones (JSON)")
            print("  [P] 👤 Cambiar Perfil")
            print("  [E] 🚪 Salir")
            print("========================================")
            
            opcion = input("Elegí una opción: ").strip().upper()
            
            if opcion == 'C': ejecutar_cruce(perfil_actual)
            elif opcion == 'S': ejecutar_stock(perfil_actual)
            elif opcion == 'K': menu_configuracion(perfil_actual)
            elif opcion == 'R': menu_reports(perfil_actual)
            elif opcion == 'P': perfil_actual = seleccionar_perfil(perfil_actual)
            elif opcion == 'E': sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Operación abortada. Saliendo de forma segura...")
        sys.exit(0)
