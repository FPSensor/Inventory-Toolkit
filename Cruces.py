"""
Inventory Toolkit

Cross-Check (Cruces) Module (Fully Abstracted)

Author: Gonzalo

License: MIT

Repository:
https://github.com/FPSensor/Inventory-Toolkit

"""

VERSION = "1.1.0"
import pandas as pd
import numpy as np
import argparse
import sys
import os

# 1. Importamos nuestro nuevo servicio de configuración
from core.configuration_manager import ConfigurationManager

# Por defecto cargará 'profile/demo/configs/'
config = ConfigurationManager()

# =========================================================================
# CORE FUNCTIONS
# =========================================================================
def clasificar_familia(codigo, familias_dict, familia_por_defecto):
    """Assigns a family category based on prefix matching from external config."""
    codigo = str(codigo).strip().upper()
    
    # Aplanamos el diccionario { "Familia": ["prefijo1", "prefijo2"] } 
    # a una lista de tuplas (prefijo, Familia)
    reglas = []
    for familia, prefijos in familias_dict.items():
        for prefijo in prefijos:
            reglas.append((str(prefijo).strip().upper(), familia))
            
    # Ordenamos por longitud del prefijo (de mayor a menor) para que "10" se evalúe antes que "1"
    reglas.sort(key=lambda x: len(x[0]), reverse=True)
    
    for prefijo, familia in reglas:
        if codigo.startswith(prefijo):
            return familia
            
    return familia_por_defecto

def aplicar_exclusiones(df, exclusions_dict, col_articulo):
    """Filters out excluded articles and keywords based on config."""
    excluded_articles = exclusions_dict.get("excluded_articles", [])
    excluded_keywords = exclusions_dict.get("excluded_keywords", [])
    
    if col_articulo in df.columns:
        # Filtrar por artículos exactos
        df = df[~df[col_articulo].isin(excluded_articles)]
        
        # Filtrar por palabras clave en la columna principal
        for keyword in excluded_keywords:
            df = df[~df[col_articulo].astype(str).str.contains(keyword, case=False, na=False)]
            
    return df

def procesar_precios(ruta_archivo, pricing_dict):
    """Reads and processes pricing lists using dynamic column names."""
    if not ruta_archivo or not os.path.exists(ruta_archivo):
        return None
        
    try:
        df = pd.read_excel(ruta_archivo)
        df['Artículo'] = df['Artículo'].astype(str).str.split(' ').str[0]
        
        columnas_esperadas = pricing_dict.get("columnas_esperadas", [])
        renombres = pricing_dict.get("mapeo_nombres", {})
        
        for col in columnas_esperadas:
            if col not in df.columns:
                print(f"WARNING: Missing column '{col}' in {ruta_archivo}.")
                return None
                
        df = df[columnas_esperadas].rename(columns=renombres)
        columna_base = list(renombres.values())[0] if renombres else "Base"
        
        df_pivot = pd.pivot_table(
            df, index='Artículo', columns=columna_base, values='Precio', aggfunc='mean'
        ).reset_index()
        return df_pivot
    except Exception as e:
        print(f"ERROR processing {ruta_archivo}: {e}")
        return None

# =========================================================================
# MAIN EXECUTION
# =========================================================================
def procesar_cruces(args):
    if not hasattr(args, 'input') or not args.input or not os.path.exists(args.input):
        print(f"ERROR: Data file '{getattr(args, 'input', 'Unknown')}' not found.")
        sys.exit(1)

    print("Loading external configurations...")
    
    # 2. Instanciamos el manager centralizado
    try:
        cfg = ConfigurationManager("configs")
    except ConfigurationError as e:
        print(f"\nCRITICAL CONFIGURATION ERROR:\n{e}")
        sys.exit(1)

    # 3. Asignación directa usando el manager
    familias_dict = cfg.familias._data
    databases_dict = cfg.databases._data
    exclusions_dict = cfg.cruces.exclusions
    
    # Intentamos sacar la configuración de precios de cruces, sino usamos la de stocks
    pricing_dict = getattr(cfg.cruces, 'pricing', getattr(cfg.stocks, 'pricing', {}))
    
    # Mapeo dinámico de variables
    col_articulo = cfg.cruces.settings.get("columna_articulo", "Item")
    col_familia = cfg.cruces.settings.get("columna_familia", "Category")
    familia_defecto = cfg.cruces.settings.get("familia_por_defecto", "Uncategorized")
    calcular_dif = cfg.cruces.settings.get("calcular_diferencias", False)
    prefijo_dif = cfg.cruces.settings.get("prefijo_diferencia", "Diff_")

    print(f"Starting Cross-Check processing for {args.input}...")
    try:
        df_cruces = pd.read_excel(args.input)
    except Exception as e:
        print(f"ERROR reading Excel file: {e}")
        sys.exit(1)
    
    # Limpieza inicial dinámica
    if col_articulo in df_cruces.columns:
        df_cruces[col_articulo] = df_cruces[col_articulo].astype(str).str.strip()
    else:
        print(f"WARNING: Main column '{col_articulo}' not found in the dataset. Some operations will be skipped.")
    
    print("Applying exclusion rules...")
    df_cruces = aplicar_exclusiones(df_cruces, exclusions_dict, col_articulo)
    
    print("Classifying families...")
    if col_articulo in df_cruces.columns:
        df_cruces[col_familia] = df_cruces[col_articulo].apply(lambda x: clasificar_familia(x, familias_dict, familia_defecto))
    
    print("Processing pricing files for differences valuation...")
    df_costo = procesar_precios(getattr(args, 'costo', None), pricing_dict)
    df_venta = procesar_precios(getattr(args, 'venta', None), pricing_dict)
    
    # Merge de precios de costo
    if df_costo is not None:
        renombres_costo = {col: f"PrecioUnit.Costo.{col}" for col in df_costo.columns if col != 'Artículo'}
        df_costo = df_costo.rename(columns=renombres_costo)
        df_cruces = pd.merge(df_cruces, df_costo, left_on=col_articulo, right_on='Artículo', how='left')

    # Merge de precios de venta
    if df_venta is not None:
        renombres_venta = {col: f"PrecioUnit.Venta.{col}" for col in df_venta.columns if col != 'Artículo'}
        df_venta = df_venta.rename(columns=renombres_venta)
        df_cruces = pd.merge(df_cruces, df_venta, left_on=col_articulo, right_on='Artículo', how='left')

    # Limpiamos la columna extra 'Artículo' generada por el merge si era distinta a la principal
    if col_articulo != 'Artículo' and 'Artículo' in df_cruces.columns:
        df_cruces = df_cruces.drop(columns=['Artículo'])

    cols_precios = [c for c in df_cruces.columns if c.startswith('PrecioUnit.')]
    df_cruces[cols_precios] = df_cruces[cols_precios].fillna(0).astype(float)
    
    print("Mapping databases and calculating differences...")
    for local, deposito in databases_dict.items():
        if local in df_cruces.columns and deposito in df_cruces.columns:
            if calcular_dif:
                col_nombre_diferencia = f"{prefijo_dif}{local}"
                df_cruces[col_nombre_diferencia] = df_cruces[local] - df_cruces[deposito]
                
                # Valuation of the difference
                col_costo = f"PrecioUnit.Costo.{local}"
                col_venta = f"PrecioUnit.Venta.{local}"
                
                if col_costo in df_cruces.columns:
                    df_cruces[f"Dif_Costo_{local}"] = df_cruces[col_nombre_diferencia] * df_cruces[col_costo]
                if col_venta in df_cruces.columns:
                    df_cruces[f"Dif_Venta_{local}"] = df_cruces[col_nombre_diferencia] * df_cruces[col_venta]

    # Opcional: Limpiar las columnas de Precio Unitario para no ensuciar el reporte final
    df_cruces = df_cruces.drop(columns=cols_precios, errors='ignore')

    print("Generating report...")
    df_cruces.to_excel(args.out, index=False)
    print(f"SUCCESS: Cross-check completed! File saved at: {args.out}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Agnostic Inventory Cross-Check Tool.")
    parser.add_argument('-input', required=True, help="Path to the input Excel file")
    parser.add_argument('-costo', default=None, help="Path to Costo.xlsx file (Optional)")
    parser.add_argument('-venta', default=None, help="Path to Venta.xlsx file (Optional)")
    parser.add_argument('-out', default="Cruces_Resultados.xlsx", help="Output file path")
    
    args = parser.parse_args()
    procesar_cruces(args)