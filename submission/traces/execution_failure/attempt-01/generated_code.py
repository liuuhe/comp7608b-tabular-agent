import pandas as pd
tables = {}
notes = []
data = inputs['ratio_workclass_capital'].copy()
grouped = data.groupby(['workclass'], observed=True, dropna=True)
aggregated = grouped.agg({'capital-gain': 'sum', 'capital-loss': 'sum', 'valid_count': 'size'}, include='all')
result = aggregated.assign(value=lambda x: x['capital-gain'] / x['capital-loss']).drop(columns=['capital-gain', 'capital-loss'])
result['value'] = result['value'].replace([np.inf, -np.inf], np.nan)
result = result.sort_values(['value'], ascending=[True], na_position='last', kind='mergesort')
tables['ratio_workclass_capital'] = result.copy()
