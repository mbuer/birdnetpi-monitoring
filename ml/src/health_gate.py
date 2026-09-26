import pandas as pd


UNRELIABLE_HEALTH_STATES = {"incomplete", "unknown"}


def mask_unreliable_zero(
    frame: pd.DataFrame,
    value_column: str,
    columns_to_mask: list[str] | None = None,
) -> pd.DataFrame:
    """Mask zero observations only when explicit health evidence is unreliable.

    Hours with no station-health row are left unchanged so legacy pre-health
    history remains usable. Positive observations are also preserved even when
    health evidence is incomplete or unknown.
    """
    data = frame.copy()

    if "health_state" not in data.columns:
        return data

    values = pd.to_numeric(data[value_column], errors="coerce")
    unreliable_zero = (
        data["health_state"].isin(UNRELIABLE_HEALTH_STATES)
        & values.eq(0)
    )

    if columns_to_mask is None:
        columns_to_mask = [value_column]

    data.loc[unreliable_zero, columns_to_mask] = pd.NA

    return data
