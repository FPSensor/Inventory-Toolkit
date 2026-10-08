"""Stable recovery contracts; presentation never parses exception messages."""
from enum import Enum
from core.configuration_errors import ConfigurationError


class ErrorCode(str, Enum):
    CONFIG_REQUIRED_FIELD = 'CONFIG_REQUIRED_FIELD'
    CONFIG_INVALID = 'CONFIG_INVALID'
    INPUT_COLUMN_MISSING = 'INPUT_COLUMN_MISSING'
    SETUP_STATE_INVALID = 'SETUP_STATE_INVALID'


class WorkflowError(ConfigurationError):
    def __init__(self, code, message, *, module=None, step=None, field=None, details=None):
        self.code = ErrorCode(code)
        self.module = module
        self.step = step
        self.field = field
        self.details = details or {}
        super().__init__(message)

    @property
    def can_configure(self):
        return bool(self.module and self.step and self.code in {
            ErrorCode.CONFIG_REQUIRED_FIELD, ErrorCode.CONFIG_INVALID,
        })
