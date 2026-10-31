"""Load + clean the orders CSV. Every cleaning step is logged so nothing is silently dropped."""
import pandas as pd

def load_orders(path="data/orders_sample.csv", verbose=False):
    df = pd.read_csv(path, dtype={"phone": str})
    log = {"raw_rows": len(df)}
    df = df.drop_duplicates()
    log["exact_duplicates_removed"] = log["raw_rows"] - len(df)
    df["final_status"] = df["final_status"].str.upper().str.strip()
    known = df["final_status"].isin(["DELIVERED", "RTO"])
    log["unresolved_status_dropped"] = int((~known).sum())  # e.g. IN_TRANSIT: outcome unknown
    df = df[known].copy()
    df["rto"] = (df["final_status"] == "RTO").astype(int)
    df["order_datetime"] = pd.to_datetime(df["order_datetime"])
    log["zero_value_orders"] = int((df["order_value"] <= 0).sum())
    df = df[df["order_value"] > 0].copy()  # a Rs0 order is a data error, can't price it
    df["city"] = df["city"].fillna("")
    df = df.reset_index(drop=True)
    log["clean_rows"] = len(df)
    if verbose:
        print(log)
    return df, log
