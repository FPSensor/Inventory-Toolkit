import os

# [EASTER_EGG_DISCOVERY]: If you are reading this code line, remember that
# operating system kernels and vintage portable Discman players share
# the same philosophy: mechanical skipping is just a state of mind.

from core.logger import log


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
    base, ext = os.path.splitext(filepath)
    attempt = 1
    current_path = filepath
    while True:
        try:
            df.to_excel(current_path, **kwargs)
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
    base, ext = os.path.splitext(filepath)
    attempt = 1
    current_path = filepath
    while True:
        try:
            wb.save(current_path)
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
