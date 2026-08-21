import pandas as pd

def build_feature_dataset(
    events: pd.DataFrame,
    products: pd.DataFrame,
) -> pd.DataFrame:

    events = events[['user_id', 'product_id']].copy()

    event_product = pd.merge(events, products, on='product_id', 
                             how='left', validate='many_to_one')

    event_product['interactions'] = (event_product.groupby(['user_id', 'product_id'])
                                     ['user_id'].transform('count')
    )
    event_product['interactions_by_category'] = (event_product.groupby(['user_id', 'category'])
                                         ['user_id'].transform('count')
    )

    max_affinity = (
        event_product.sort_values(['user_id', 'interactions_by_category'], ascending=[True, False])
        .drop_duplicates('user_id')[['user_id', 'category']]
        .rename(columns={'category': 'user_affinity_category'})
    )

    users = events[['user_id']].drop_duplicates()
    feature_df = pd.merge(users, products, how='cross')

    interactions = (event_product[['user_id', 'product_id', 'interactions']]
                    .drop_duplicates(['user_id', 'product_id'])
    )
    feature_df = pd.merge(feature_df, interactions, on=['user_id', 'product_id'], 
                      how='left', validate='one_to_one')

    feature_df['interactions'] = feature_df['interactions'].fillna(0).astype(int)

    feature_df = pd.merge(feature_df, max_affinity, on='user_id', 
                          how='left', validate='many_to_one')

    feature_df['user_affinity_match'] = (
        feature_df['category'] == feature_df['user_affinity_category']
    ).astype(int)

    feature_df = feature_df.drop(columns=['user_affinity_category'])

    return feature_df