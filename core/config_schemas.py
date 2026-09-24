"""
config_schemas.py — Pydantic schemas for profile configuration validation.

The schemas intentionally preserve unknown keys so profile extensions remain
forward-compatible instead of being silently discarded during validation.
"""

from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field, RootModel


class _FlexibleConfig(BaseModel):
  """Base config that validates known fields without dropping extensions."""

  model_config = ConfigDict(extra='allow')


class FamiliasConfig(RootModel[Dict[str, List[str]]]):
  """familias.json is a root mapping: family name -> SKU prefixes."""


class StoresConfig(_FlexibleConfig):
  locales_activos: List[str] = Field(default_factory=list)
  grupos_regionales: Dict[str, List[str]] = Field(default_factory=dict)


class CleaningConfig(_FlexibleConfig):
  columnas_a_eliminar: List[str] = Field(default_factory=list)
  columnas_texto_a_limpiar: List[str] = Field(default_factory=list)
  columnas_a_formatear: List[str] = Field(default_factory=list)


class PricingConfig(_FlexibleConfig):
  columnas_esperadas: List[str] = Field(default_factory=list)
  mapeo_nombres: Dict[str, str] = Field(default_factory=dict)
  margen_defecto: float = 0.0


class CrossCheckSettings(_FlexibleConfig):
  articulos_ignorados: List[str] = Field(default_factory=list)
  palabras_ignoradas: List[str] = Field(default_factory=list)
  columnas_costo: Dict[str, str] = Field(default_factory=dict)
  columnas_venta: Dict[str, str] = Field(default_factory=dict)
  tolerancia: float = 0.0


class YoYReportsConfig(_FlexibleConfig):
  # The same reports.json also contains Stock Processing report layout.
  orden_columnas_base: List[str] = Field(
      default_factory=lambda: ['Artículo', 'Familias']
  )
  hoja_datos_crudos: str = 'Datos'
  resumenes: List[Dict[str, Any]] = Field(default_factory=list)

  output_path: str = 'analysis_report.xlsx'
  data_source: Dict[str, Any] = Field(default_factory=dict)
  report_structures: Dict[str, List[str]] = Field(default_factory=dict)