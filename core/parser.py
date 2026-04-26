import pandas as pd

def parse_addresses(filepath: str) -> list[str]:
    """Load CSV or Excel and return list of address strings."""
    if filepath.endswith(".csv"):
        df = pd.read_csv(filepath)
    else:
        df = pd.read_excel(filepath)
    return df["address"].dropna().tolist()
