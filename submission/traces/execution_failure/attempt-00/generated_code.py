import pandas as pd
tables = {}
notes = []
data = inputs['ratio_workclass_capital'].copy()
grouped = data.groupby(['workclass'], observed=True, dropna=True)
result = grouped[['capital-gain', 'capital-loss']].apply(lambda g: pd.Series({'value': g['capital-gain'].sum() / g['capital-loss'].sum(), 'valid_count': len(g)}), include=False)
result.columns = ['value', 'valid_count']
result['workclass'] = result.index
result = result.sort_values(['value'], ascending=[True], na_position='last', kind='mergesort')
tables['ratio_workclass_capital'] = result.copy()
