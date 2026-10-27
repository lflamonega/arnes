"""User-facing errors that do not require terminating the session."""


class ArnesError(Exception):
    pass


class ProviderError(ArnesError):
    pass


class ValidationError(ArnesError):
    pass
