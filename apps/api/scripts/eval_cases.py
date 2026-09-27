"""Back-compat shim: the dataset now lives in app/services/sample_data.py so the
app itself can load it (onboarding "Try with sample data")."""

from app.services.sample_data import CASES, REPO

__all__ = ["CASES", "REPO"]
