import sys
from cli.utils import limpiar_pantalla
from cli.profiles import seleccionar_perfil
from cli.config_menu import menu_configuracion
from cli.cruces import ejecutar_cruce
from cli.stocks import ejecutar_stock
from cli.wizard import PANDAS_DISPONIBLE

# Comprobación de desarrollo al iniciar
try:
    from engine import Stocks
    from engine import Cruces
    MODULOS_CARGADOS = True
except ImportError as e:
    MODULOS_CARGADOS = False
    error_msg = e

def main():
    if not PANDAS_DISPONIBLE:
        print("⚠️ Advertencia: Pandas no está instalado. El auto-mapeo inteligente estará desactivado.")
    
    if not MODULOS_CARGADOS:
        print(f"⚠️ Advertencia: No se pudieron cargar los módulos base ({error_msg}).")
        print("Asegurate de que la carpeta 'engine/' exista y contenga Stocks.py y Cruces.py.")
        input("Presioná Enter para iniciar el menú en modo degradado...")

    perfil_actual = None
    
    try:
        # Obligamos al usuario a seleccionar o crear un perfil al iniciar
        perfil_actual = seleccionar_perfil(perfil_actual, inicio=True)
        
        while True:
            limpiar_pantalla()
            print("========================================")
            print("       INVENTORY TOOLKIT v2.0 CLI       ")
            print(f"       Perfil Activo: [{perfil_actual}]  ")
            print("========================================")
            print("¿Qué querés hacer hoy?\n")
            print("  [C] 🔄 Cruce de Inventario")
            print("  [S] 📦 Procesamiento de Stock")
            print("  [K] ⚙️  Configuraciones (JSON)")
            print("  [P] 👤 Cambiar Perfil")
            print("  [E] 🚪 Salir")
            print("========================================")

            opcion = input("Elegí una opción: ").strip().upper()

            if opcion == 'C':
                ejecutar_cruce(perfil_actual)
            elif opcion == 'S':
                ejecutar_stock(perfil_actual)
            elif opcion == 'K':
                menu_configuracion(perfil_actual)
            elif opcion == 'P':
                perfil_actual = seleccionar_perfil(perfil_actual)
            elif opcion == 'E':
                print("\nSaliendo del toolkit. ¡Nos vemos!")
                sys.exit(0)
            else:
                print("\n❌ Opción no válida. Por favor, ingresá C, S, K, P o E.")
                input("Presioná Enter para intentar de nuevo...")
    
    except KeyboardInterrupt:
        print("\n\n⚠️ Operación abortada por el usuario (Ctrl+C). Saliendo limpiamente...")
        sys.exit(0)