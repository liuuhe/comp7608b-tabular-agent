import pandas as pd
tables = {}
notes = []
data = inputs['a1'].copy()
result = data.groupby(['Country'], observed=True, dropna=True)['UnitPrice'].agg(value='mean', valid_count='count').reset_index()
result = result.sort_values(['Country', 'value', 'valid_count'], ascending=[True, True, True], na_position='last', kind='mergesort')
tables['a1'] = result.copy()
