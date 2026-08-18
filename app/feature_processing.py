import pandas as pd


def build_feature_dataset(
    events: pd.DataFrame,
    products: pd.DataFrame,
) -> pd.DataFrame:
    
    interactions = (
        events
        .groupby(["user_id", "product_id"])
        .size()
        .reset_index(name="interactions")
    )

    events_with_products = events.merge(
        products[["product_id", "category"]],
        on="product_id",
        how="left",
    )

    user_category_counts = (
        events_with_products
        .groupby(["user_id", "category"])
        .size()
        .reset_index(name="category_interactions")
    )

    user_affinity = (
        user_category_counts
        .sort_values(
            ["user_id", "category_interactions"],
            ascending=[True, False],
        )
        .drop_duplicates("user_id")
        [["user_id", "category"]]
        .rename(columns={"category": "user_affinity_category"})
    )

    users = events[["user_id"]].drop_duplicates()

    user_products = users.merge(
        products,
        how="cross",
    )

    feature_df = user_products.merge(
        interactions,
        on=["user_id", "product_id"],
        how="left",
    )

    feature_df["interactions"] = (
        feature_df["interactions"]
        .fillna(0)
        .astype(int)
    )

    feature_df = feature_df.merge(
        user_affinity,
        on="user_id",
        how="left",
    )

    feature_df["user_affinity_match"] = (
        feature_df["category"]
        == feature_df["user_affinity_category"]
    ).astype(int)

    return feature_df