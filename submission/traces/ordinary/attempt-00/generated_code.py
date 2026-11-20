import pandas as pd
tables = {}
notes = []
data = inputs['total_rentals_count'].copy()
result = pd.DataFrame([{'value':data['rentals'].sum(),'valid_count':int(data['rentals'].count())}])
result = result.sort_values(['valid_count'],ascending=[True],na_position='last',kind='mergesort')
tables['total_rentals_count'] = result.copy()
data = inputs['rentals_by_weather'].copy()
result = data.groupby(['weather'],observed=True,dropna=True)['rentals'].agg(value='sum',valid_count='count').reset_index()
result = result.sort_values(['value'],ascending=[True],na_position='last',kind='mergesort')
tables['rentals_by_weather'] = result.copy()
