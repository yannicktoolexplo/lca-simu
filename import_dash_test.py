import plotly.graph_objects as go

# Example data for electrical consumption, water consumption, mineral, and metal used
categories = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
electrical_consumption = [300, 280, 290, 310, 320, 300, 290, 280, 270, 260, 250, 240]
water_consumption = [200, 190, 195, 205, 210, 200, 195, 190, 185, 180, 175, 170]
minerals_used = [100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155]
metals_used = [50, 55, 53, 57, 59, 61, 63, 65, 67, 69, 71, 73]

# Create the plot using plotly.graph_objects
fig = go.Figure()

# Add traces for each type of consumption
fig.add_trace(go.Scatter(x=categories, y=electrical_consumption, fill='tozeroy', name='Electrical Consumption', fillcolor='rgba(0, 0, 255, 0.2)', marker={'color': 'rgba(0, 0, 255, 1)'}))
fig.add_trace(go.Scatter(x=categories, y=water_consumption, fill='tozeroy', name='Water Consumption', fillcolor='rgba(0, 255, 0, 0.2)', marker={'color': 'rgba(0, 255, 0, 1)'}))
fig.add_trace(go.Scatter(x=categories, y=minerals_used, fill='tozeroy', name='Minerals Used', fillcolor='rgba(255, 0, 0, 0.2)', marker={'color': 'rgba(255, 0, 0, 1)'}))
fig.add_trace(go.Scatter(x=categories, y=metals_used, fill='tozeroy', name='Metals Used', fillcolor='rgba(255, 165, 0, 0.2)', marker={'color': 'rgba(255, 165, 0, 1)'}))

# Update layout
fig.update_layout(title='Resource Consumption over Time', xaxis_title='Months', yaxis_title='Consumption')

# Show the plot
fig.show()
