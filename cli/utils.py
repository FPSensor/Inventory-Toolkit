import os
import sys
import json
import subprocess
import tkinter as tk
from tkinter import filedialog

def limpiar_pantalla():
    """Limpia la consola dependiendo del sistema operativo."""
    os.system('cls' if os.name == 'nt' else 'clear')

def preguntar_si_no(mensaje):
    """Fuerza al usuario a responder S o N."""
    while True:
        respuesta = input(f"{mensaje} [S/N]: ").strip().upper()
        if respuesta == 'S':
            return True
        if respuesta == 'N':
            return False
        print("❌ Opción inválida. Ingresá 'S' para Sí o 'N' para No.")

def preguntar_archivo(mensaje, valor_por_defecto, es_salida=False):
    """Pide un archivo. Permite escribir, usar default o abrir explorador."""
    respuesta = input(f"{mensaje} (Enter: '{valor_por_defecto}', 'B' para Explorador): ").strip()
    
    if respuesta.upper() == 'B':
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        if es_salida:
            ruta = filedialog.asksaveasfilename(
                title="Guardar resultado como...",
                initialfile=valor_por_defecto,
                defaultextension=".xlsx",
                filetypes=[("Archivos Excel", "*.xlsx *.xls")]
            )
        else:
            ruta = filedialog.askopenfilename(
                title="Seleccioná el archivo",
                filetypes=[("Archivos Excel", "*.xlsx *.xls"), ("Todos los archivos", "*.*")]
            )
        root.destroy()
        
        if ruta:
            print(f"📁 Archivo seleccionado: {ruta}")
            return ruta
        else:
            print(f"⚠️ Selección cancelada. Se usará el valor por defecto.")
            return valor_por_defecto

    return respuesta if respuesta else valor_por_defecto

def validar_archivos_existen(lista_archivos):
    """Verifica físicamente en el disco si los archivos existen."""
    todos_existen = True
    for archivo in lista_archivos:
        if archivo and not os.path.isfile(archivo):
            print(f"❌ Error: El archivo '{archivo}' no existe en esta ruta.")
            todos_existen = False
    return todos_existen

def abrir_en_editor(ruta):
    """Abre el archivo en el editor de texto predeterminado del sistema."""
    print(f"Abriendo {os.path.basename(ruta)} en tu editor predeterminado...")
    try:
        if sys.platform.startswith('darwin'):
            subprocess.call(('open', ruta))
        elif os.name == 'nt':
            os.startfile(ruta)
        elif os.name == 'posix':
            subprocess.call(('xdg-open', ruta))
    except Exception as e:
        print(f"❌ No se pudo abrir el archivo automáticamente: {e}")
    input("\nPresioná Enter cuando hayas terminado de editar y guardado los cambios...")

def cargar_json(ruta):
    try:
        with open(ruta, 'r', encoding='utf-8') as archivo:
            return json.load(archivo)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        print(f"❌ El archivo {ruta} está corrupto o no es un JSON válido.")
        return None

def guardar_json(ruta, datos):
    try:
        with open(ruta, 'w', encoding='utf-8') as archivo:
            json.dump(datos, archivo, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Error al guardar el archivo: {e}")