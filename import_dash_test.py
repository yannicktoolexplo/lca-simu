import plotly.graph_objects as go

categories = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

energy_data = {'x': categories, 'y': [29.8, 28, 24.9, 21.5, 27.4, 27.2, 22.1, 29.9, 25.6, 26.4, 23.1, 25.3], 'type': 'scatter', 'name': 'Energy', 'fill': 'tozeroy', 'fillcolor': 'rgba(255, 0, 0, 0.2)', 'marker': {'color': 'rgba(255, 0, 0, 1)'}}
transportation_data = {'x': categories, 'y': [15.2, 19.8, 17.1, 16.7, 18.8, 15, 19.5, 19.4, 16.9, 16.7, 15.3, 16.6], 'type': 'scatter', 'name': 'Transportation', 'fill': 'tozeroy', 'fillcolor': 'rgba(0, 255, 0, 0.2)', 'marker': {'color': 'rgba(0, 255, 0, 1)'}}
waste_data = {'x': categories, 'y': [7.1, 6.2, 7.1, 7.6, 7.9, 7.6, 6, 7.9, 6.5, 6.3, 6.6, 6.4], 'type': 'scatter', 'name': 'Waste', 'fill': 'tozeroy', 'fillcolor': 'rgba(0, 0, 255, 0.2)', 'marker': {'color': 'rgba(0, 0, 255, 1)'}}


fig = go.Figure(data=[energy_data, transportation_data, waste_data])
fig.update_layout(title='Energy, Transportation, and Waste Emissions')
fig.update_xaxes(title='Categories')
fig.update_yaxes(title='Emissions')

fig.show()