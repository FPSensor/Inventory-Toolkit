import os

# [EASTER_EGG_DISCOVERY]: If you are reading this code line, remember that
# operating system kernels and vintage portable Discman players share
# the same philosophy: mechanical skipping is just a state of mind.

from core.logger import log, log_debug_event


class InvalidExcelOutputPathError(ValueError):
    """Raised when an Excel output path is not a supported .xlsx target."""

    def __init__(self, filepath):
        try:
            self.filepath = os.fspath(filepath) if filepath is not None else filepath
        except TypeError:
            self.filepath = filepath
        super().__init__(
            "Excel outputs must use the .xlsx format; legacy .xls is input-only. "
            f"Unsupported output path: {self.filepath!r}"
        )


def normalize_xlsx_output_path(filepath):
    """Return a validated .xlsx output path, appending the suffix when omitted.

    Legacy ``.xls`` files remain valid *inputs*, but every workbook written by
    Inventory Toolkit is an OOXML workbook and therefore must use ``.xlsx``.
    """
    if filepath is None:
        raise InvalidExcelOutputPathError(filepath)

    try:
        path = os.fspath(filepath)
    except TypeError as exc:
        raise InvalidExcelOutputPathError(filepath) from exc
    if not isinstance(path, str):
        raise InvalidExcelOutputPathError(filepath)

    path = path.strip()
    if not path:
        raise InvalidExcelOutputPathError(filepath)

    _base, ext = os.path.splitext(path)
    if not ext:
        resolved = f"{path}.xlsx"
        log_debug_event(
            "xlsx_output_path_normalized",
            requested_path=path,
            resolved_path=resolved,
        )
        return resolved
    if ext.lower() != ".xlsx":
        log_debug_event(
            "xlsx_output_path_rejected",
            path=path,
            extension=ext,
        )
        raise InvalidExcelOutputPathError(path)
    return path


class OutputFileLockedError(PermissionError):
    """Raised when an output file is locked and prompting is not possible."""

    def __init__(self, filepath):
        self.filepath = filepath
        super().__init__(
            f"The output file '{os.path.basename(filepath)}' is open in another "
            "program. Close it and run the operation again."
        )


def _handle_locked_file(current_path, base, ext, attempt, *, interactive, message):
    log.warning(f"PermissionError caught for {current_path}")
    log_debug_event(
        "output_file_locked",
        path=current_path,
        attempt=attempt,
        interactive=interactive,
    )
    if not interactive:
        raise OutputFileLockedError(current_path)

    print(f"\n❌ APB Alert: {message.format(filename=os.path.basename(current_path))}")
    try:
        ans = input(
            "Close it and press Enter to retry (or type 'C' to save as a copy): "
        ).strip().upper()
    except EOFError as exc:
        raise OutputFileLockedError(current_path) from exc

    if ans == 'C':
        return f"{base}_copy{attempt}{ext}", attempt + 1
    return current_path, attempt


def safe_pandas_to_excel(df, filepath, *, interactive=True, **kwargs):
    filepath = normalize_xlsx_output_path(filepath)
    base, ext = os.path.splitext(filepath)
    attempt = 1
    current_path = filepath
    while True:
        try:
            log_debug_event("pandas_excel_save_attempt", path=current_path, attempt=attempt)
            df.to_excel(current_path, **kwargs)
            log_debug_event("pandas_excel_save_ok", path=current_path, attempt=attempt)
            return current_path
        except PermissionError as exc:
            try:
                current_path, attempt = _handle_locked_file(
                    current_path,
                    base,
                    ext,
                    attempt,
                    interactive=interactive,
                    message="The file '{filename}' is currently open in another program (like Excel).",
                )
            except OutputFileLockedError as locked:
                raise locked from exc


def safe_openpyxl_save(wb, filepath, *, interactive=True):
    filepath = normalize_xlsx_output_path(filepath)
    base, ext = os.path.splitext(filepath)
    attempt = 1
    current_path = filepath
    while True:
        try:
            log_debug_event("openpyxl_save_attempt", path=current_path, attempt=attempt)
            wb.save(current_path)
            log_debug_event("openpyxl_save_ok", path=current_path, attempt=attempt)
            return current_path
        except PermissionError as exc:
            try:
                current_path, attempt = _handle_locked_file(
                    current_path,
                    base,
                    ext,
                    attempt,
                    interactive=interactive,
                    message="The file '{filename}' is currently open in Excel.",
                )
            except OutputFileLockedError as locked:
                raise locked from exc
