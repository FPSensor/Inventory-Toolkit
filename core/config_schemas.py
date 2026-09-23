"""
config_schemas.py — Schemas de Pydantic para validación de configuración.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FamiliasConfig(BaseModel):
  root: Dict[str, List[str]] = Field(default_factory=dict)


class StoresConfig(BaseModel):
  locales_activos: List[str] = Field(default_factory=list)


class CleaningConfig(BaseModel):
  columnas_a_eliminar: List[str] = Field(default_factory=list)
  columnas_texto_a_limpiar: List[str] = Field(default_factory=list)
  columnas_a_formatear: List[str] = Field(default_factory=list)


class PricingConfig(BaseModel):
  margen_defecto: float = 0.0


class CrossCheckSettings(BaseModel):
  tolerancia: float = 0.0


class YoYReportsConfig(BaseModel):
  data_source: Dict[str, Any] = Field(default_factory=dict)
  report_structures: Dict[str, List[str]] = Field(default_factory=dict)
  output_path: str = "analysis_report.xlsx"