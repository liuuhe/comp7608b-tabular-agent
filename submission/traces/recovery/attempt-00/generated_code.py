import pandas as pd
tables = {}
notes = []
data = inputs['a1'].copy()
result = data.groupby(['Country'], observed=True, dropna=True)['Quantity'].agg(value='sum', valid_count='count').reset_index()
result = result.sort_values(['Country'], ascending=[True], na_position='last', kind='mergesort')
tables['a1'] = result.copy()
