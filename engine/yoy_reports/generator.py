from core.configuration_manager import ConfigurationManager
from core.logger import log
from engine.shared.families import build_family_rules
from engine.yoy_reports.data_processor import process_sales_data
from engine.yoy_reports.excel_renderer import render_yoy_sales_excel


def generate_sales_report(
    yoy_file_path,
    yoy_output_path,
    yoy_start_dt,
    yoy_end_dt,
    yoy_config,
    yoy_grouping_col,
    yoy_segmented,
    yoy_has_families,
    profile,
    yoy_include_sizes=False,
):
  family_rules = None
  if not yoy_has_families:
    log.info("Loading family rules to dynamically generate groupings...")
    cm = ConfigurationManager(profile)
    fam_dict = cm.get_config('familias')
    family_rules = build_family_rules(fam_dict)

  log.info(f"Reading data from {yoy_file_path} and filtering dates...")
  yoy_df_curr, yoy_df_prev, yoy_start_prev = process_sales_data(
      yoy_file_path, yoy_start_dt, yoy_end_dt, yoy_config, family_rules
  )

  log.info("Calculating YoY metrics and rendering Excel file...")
  final_path = render_yoy_sales_excel(
      yoy_output_path,
      yoy_df_curr,
      yoy_df_prev,
      yoy_start_dt,
      yoy_end_dt,
      yoy_start_prev,
      yoy_config,
      yoy_grouping_col,
      yoy_segmented,
      yoy_include_sizes,
  )
  return final_path