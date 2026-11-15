"""Spreadsheet-safe text export; raw research records remain unchanged."""


def spreadsheet_safe(value):
    if isinstance(value,str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value
