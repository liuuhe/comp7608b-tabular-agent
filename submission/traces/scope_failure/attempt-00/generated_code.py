import pandas as pd
tables = {}
notes = []
data = inputs['a1'].copy()
result = data.groupby(['mnth'],observed=True,dropna=True)['temp'].agg(value='mean',valid_count='count').reset_index()
result = result.sort_values(['mnth'],ascending=[True],na_position='last',kind='mergesort')
tables['a1'] = result.copy()
data = inputs['a2'].copy()
result = data.groupby(['mnth'],observed=True,dropna=True)['temp'].agg(value='count',valid_count='count').reset_index()
result = result.sort_values(['mnth'],ascending=[True],na_position='last',kind='mergesort')
tables['a2'] = result.copy()
