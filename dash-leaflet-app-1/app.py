from dash import Dash, dcc, html, Input, Output, State
import dash_leaflet as dl
import psycopg2
from datetime import datetime
import pandas as pd
import math

# Database connection string
conn_string = "host='localhost' dbname='vesselDB' user='postgres' password='root'"

# Predefined list of 100 fixed hex colors
fixed_colors = [
    "#FF5733", "#33FF57", "#3357FF", "#FF33A1", "#A133FF", "#33FFF5", "#F5FF33", "#FF8C33", "#8C33FF", "#33FF8C",
    "#FF3333", "#33FF33", "#3333FF", "#FF33FF", "#33FFFF", "#FFFF33", "#FF6633", "#6633FF", "#33FF66", "#FF3366",
    "#66FF33", "#3366FF", "#FF9933", "#9933FF", "#33FF99", "#FF3399", "#99FF33", "#3399FF", "#FFCC33", "#CC33FF",
    "#33FFCC", "#FF33CC", "#CCFF33", "#33CCFF", "#FF3333", "#33FF33", "#3333FF", "#FF33FF", "#33FFFF", "#FFFF33",
    "#FF6633", "#6633FF", "#33FF66", "#FF3366", "#66FF33", "#3366FF", "#FF9933", "#9933FF", "#33FF99", "#FF3399",
    "#99FF33", "#3399FF", "#FFCC33", "#CC33FF", "#33FFCC", "#FF33CC", "#CCFF33", "#33CCFF"
]

# Function to get min and max epoch times from the database
def get_min_max_epoch():
    conn = psycopg2.connect(conn_string)
    cursor = conn.cursor()
    query = "SELECT MIN(sourcedatetime), MAX(sourcedatetime) FROM vessel_tracks WHERE sourcedatetime >= 1000000000"
    cursor.execute(query)
    min_max = cursor.fetchone()
    cursor.close()
    conn.close()
    return min_max

# Function to get vessel data based on epoch range and vessel name
def get_vessel_data(start_epoch, end_epoch, vessel_name):
    conn = psycopg2.connect(conn_string)
    cursor = conn.cursor()
    query = """
    SELECT sourcedatetime, latitude, longitude FROM vessel_tracks
    WHERE sourcedatetime BETWEEN %s AND %s AND vesselname = %s
    ORDER BY sourcedatetime
    """
    cursor.execute(query, (start_epoch, end_epoch, vessel_name))
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return data

# Function to calculate bearing between two points
def calculate_bearing(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    d_lon = lon2 - lon1
    x = math.sin(d_lon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(d_lon)
    bearing = (math.degrees(math.atan2(x, y)) + 360) % 360
    return round(bearing, 2)

# Get min and max epoch times
min_epoch, max_epoch = get_min_max_epoch()

# Initialize the Dash app
app = Dash(__name__)

# App layout
app.layout = html.Div([
    html.Div(
        [
            html.H1("Vessel Tracking Dashboard", style={"text-align": "center", "color": "#214097", "font-family": "Arial, sans-serif"}),
            html.P("Monitor and analyze vessel movements in real-time.", style={"text-align": "center", 
                                                                                "color": "#555", "font-family": "Arial, sans-serif"}),
        ],
        style={"padding": "1px", "background-color": "#f4f4f4", "border-bottom": "1px solid #ddd"}
    ),
    html.Div(
        [
            html.Div(
                [
                    html.Label("Select Time Range (Epoch):", style={"font-weight": "bold", "font-family": "Arial, sans-serif"}),
                    dcc.RangeSlider(
                        id='epoch-slider',
                        min=min_epoch,
                        max=max_epoch,
                        step=1,
                        value=[min_epoch, max_epoch],
                        marks={
                            min_epoch: pd.to_datetime(min_epoch, unit='s').strftime('%Y-%m-%d %H:%M:%S'),
                            max_epoch: pd.to_datetime(max_epoch, unit='s').strftime('%Y-%m-%d %H:%M:%S')
                        },
                    ),
                    html.Div(id='datetime-display', style={"margin-top": "10px", "font-weight": "bold", "font-family": "Arial, sans-serif"}),
                ],
                style={"padding-inline": "50px","padding": "10px", "background-color": "#fff", "border": "1px solid #ddd", "border-radius": "5px", "margin-bottom": "20px"}
            ),
            html.Div(
                [
                    html.Label("Select Vessel(s):", style={"font-weight": "bold", "font-family": "Arial, sans-serif", 
                                                           "spacing": "5px", "text-decoration": "underline"}),
                    dcc.Dropdown(
                        id='vessel-dropdown',
                        options=[],
                        multi=True,  # Allow multiple vessel selection
                        placeholder='Select vessel(s)',
                        style={"font-family": "Arial, sans-serif"}
                    ),
                ],
                style={"padding-inline": "50px","padding": "10px", "background-color": "#fff", "border": "1px solid #ddd", "border-radius": "5px"}
            ),
        ],
        style={ "gap": "10px", "margin": "10px"}
    ),
    dl.Map(
        id='map',
        style={'width': '100%', 'height': '600px', "margin": "20px auto", "border": "1px solid #ddd", "border-radius": "5px"},
        center=[1.3521, 103.8198],
        zoom=6,
        children=[
            dl.TileLayer(),
            dl.MeasureControl(
                position="topleft",
                primaryLengthUnit="kilometers",
                primaryAreaUnit="hectares",
                activeColor="#214097",
                completedColor="#972158",
            ),
            dl.FeatureGroup([
                dl.LayerGroup(id='vessel-layer')
            ])
        ]
    ),
    html.Div(
        [
            html.Button("Download CSV", id="download-btn", n_clicks=0, style={"margin-top": "20px", "background-color": "#214097", "color": "#fff", "border": "none", "padding": "10px 20px", "border-radius": "5px", "cursor": "pointer", "font-family": "Arial, sans-serif"}),
            dcc.Download(id="download-dataframe-csv")
        ],
        style={"text-align": "center", "margin-bottom": "20px"}
    ),
    html.Div(
        [
            html.P("© 2025 Vessel Tracking Dashboard. All rights reserved.", style={"text-align": "center", "color": "#555", "font-size": "12px", "font-family": "Arial, sans-serif"})
        ],
        style={"padding": "10px", "background-color": "#f4f4f4", "border-top": "2px solid #ddd"}
    )
])

# Callback to update vessel dropdown based on epoch range
@app.callback(
    Output('vessel-dropdown', 'options'),
    Input('epoch-slider', 'value')
)
def update_vessel_dropdown(epoch_range):
    start_epoch, end_epoch = epoch_range
    conn = psycopg2.connect(conn_string)
    cursor = conn.cursor()
    query = """
    SELECT DISTINCT vesselname FROM vessel_tracks
    WHERE sourcedatetime BETWEEN %s AND %s
    """
    cursor.execute(query, (start_epoch, end_epoch))
    vessels = cursor.fetchall()
    cursor.close()
    conn.close()
    return [{'label': vessel[0], 'value': vessel[0]} for vessel in vessels]

# Callback to update datetime display dynamically based on RangeSlider value
@app.callback(
    Output('datetime-display', 'children'),
    Input('epoch-slider', 'value')
)
def update_datetime_display(epoch_range):
    start_epoch, end_epoch = epoch_range
    start_datetime = pd.to_datetime(start_epoch, unit='s').strftime('%Y-%m-%d %H:%M:%S')
    end_datetime = pd.to_datetime(end_epoch, unit='s').strftime('%Y-%m-%d %H:%M:%S')
    return f"Selected Datetime Range: {start_datetime} to {end_datetime}"

# Callback to update map based on selected vessels and epoch range
@app.callback(
    Output('vessel-layer', 'children'),
    Input('vessel-dropdown', 'value'),
    Input('epoch-slider', 'value')
)
def update_map(selected_vessels, epoch_range):
    start_epoch, end_epoch = epoch_range
    if selected_vessels:
        if not isinstance(selected_vessels, list):  # Ensure it's a list
            selected_vessels = [selected_vessels]
        map_elements = []
        for idx, vessel_name in enumerate(selected_vessels):
            vessel_data = get_vessel_data(start_epoch, end_epoch, vessel_name)
            if not vessel_data:
                continue

            # Extract coordinates for the polyline
            coordinates = [[row[1], row[2]] for row in vessel_data]

            # Add polyline for the vessel's track
            map_elements.append(
                dl.Polyline(
                    positions=coordinates,
                    color=fixed_colors[idx % len(fixed_colors)],  # Use fixed colors
                    weight=3,
                    opacity=0.8
                )
            )

            # Add a circle marker for the last known position
            last_position = vessel_data[-1]
            last_time = pd.to_datetime(last_position[0], unit='s').strftime('%Y-%m-%d %H:%M:%S')
            if len(vessel_data) > 1:
                second_last_position = vessel_data[-2]
                bearing = calculate_bearing(
                    second_last_position[1], second_last_position[2],
                    last_position[1], last_position[2]
                )
            else:
                bearing = 0  # Default bearing if only one position exists

            map_elements.append(
                dl.CircleMarker(
                    center=[last_position[1], last_position[2]],
                    radius=8,
                    color=fixed_colors[idx % len(fixed_colors)],  # Use fixed colors
                    fill=True,
                    fillOpacity=0.9,
                    children=[
                        dl.Tooltip(
                            html.Div(
                                [
                                    html.Div(f"Vessel Name: {vessel_name}", style={"font-weight": "bold", "color": "#214097", "margin-bottom": "5px"}),
                                    html.Div(f"Last Time: {last_time}", style={"color": "#555", "margin-bottom": "5px"}),
                                    html.Div(f"Bearing: {bearing}°", style={"color": "#555"})
                                ],
                                style={
                                    "background-color": "#fff",
                                    "padding": "10px",
                                    "border": "1px solid #ddd",
                                    "border-radius": "5px",
                                    "box-shadow": "0px 2px 5px rgba(0, 0, 0, 0.2)",
                                    "font-family": "Arial, sans-serif",
                                    "font-size": "12px",
                                    "line-height": "1.5"
                                }
                            )
                        )
                    ]
                )
            )
        return map_elements
    return []

# Callback to handle CSV download
@app.callback(
    Output('download-dataframe-csv', 'data'),
    Input('download-btn', 'n_clicks'),
    State('vessel-dropdown', 'value'),
    State('epoch-slider', 'value'),
    prevent_initial_call=True
)
def download_csv(n_clicks, selected_vessels, epoch_range):
    start_epoch, end_epoch = epoch_range
    csv_data = []
    if selected_vessels:
        if not isinstance(selected_vessels, list):  # Ensure it's a list
            selected_vessels = [selected_vessels]
        for vessel_name in selected_vessels:
            vessel_data = get_vessel_data(start_epoch, end_epoch, vessel_name)
            for row in vessel_data:
                csv_data.append({
                    "Vessel Name": vessel_name,
                    "Datetime": pd.to_datetime(row[0], unit='s').strftime('%Y-%m-%d %H:%M:%S'),
                    "Latitude": row[1],
                    "Longitude": row[2]
                })
        # Generate CSV
        df = pd.DataFrame(csv_data)
        return dcc.send_data_frame(df.to_csv, "vessel_data.csv", index=False)
    return None

if __name__ == '__main__':
    app.run(debug=True)