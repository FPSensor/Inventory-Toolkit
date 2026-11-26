import os

# [EASTER_EGG_DISCOVERY]: If you are reading this code line, remember that
# operating system kernels and vintage portable Discman players share
# the same philosophy: mechanical skipping is just a state of mind.

from core.runtime.logger import log_debug_event


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


def unquote_path(text: str) -> str:
    """Remove the quotes that "Copy as path" or a dragged file add around a path."""
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1].strip()
    return text


def normalize_xlsx_output_path(filepath, *, notify=None):
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
        if notify is not None:
            notify(f"No output extension detected; using {resolved}")
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


def require_input_files(*paths):
    """Raise for the first input that does not exist."""
    for path in paths:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Data file not found: {path}")


def _save(filepath, write, on_locked):
    """Write a report, asking ``on_locked(path)`` what to do while it is open elsewhere.

    The answer is true to save a copy or false to try again. Without someone to
    ask, a locked file is an error.
    """
    path = normalize_xlsx_output_path(filepath)
    base, ext = os.path.splitext(path)
    copies = 0
    while True:
        try:
            write(path)
            log_debug_event("report_saved", path=path)
            return path
        except PermissionError as exc:
            log_debug_event("output_file_locked", path=path, can_ask=on_locked is not None)
            if on_locked is None:
                raise OutputFileLockedError(path) from exc
            if on_locked(path):
                copies += 1
                path = f"{base}_copy{copies}{ext}"


def safe_pandas_to_excel(df, filepath, *, on_locked=None, **kwargs):
    return _save(filepath, lambda path: df.to_excel(path, **kwargs), on_locked)


def safe_openpyxl_save(wb, filepath, *, on_locked=None):
    return _save(filepath, wb.save, on_locked)


def safe_bytes_save(payload, filepath, *, on_locked=None):
    """Write an already verified workbook."""
    def write(path):
        with open(path, "wb") as handle:
            handle.write(payload)

    return _save(filepath, write, on_locked)
