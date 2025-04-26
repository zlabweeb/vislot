import dash
from dash import dcc, html, Input, Output, State, callback
import dash_leaflet as dl
import dash_leaflet.express as dlx
import plotly.graph_objects as go
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import time
import colorsys
import json  # Add this import
import math  # Also add this as it's used in haversine calculations
from dash.exceptions import PreventUpdate
from shapely.geometry import Point, Polygon

# Initialize the Dash app
app = dash.Dash(__name__)
server = app.server

# Database connection parameters
DB_CONFIG = {
    'dbname': 'vesselDB',
    'user': 'postgres',
    'password': 'root',
    'host': 'localhost'
}

# Map configuration
MAP_CENTER = [1.3521, 103.8198]  # Singapore coordinates
MAP_ZOOM = 11
MAX_VESSEL_COUNT = 100  # For color gradient scaling

# Colors
TRACK_COLORS = [
    "#FF5733", "#33FF57", "#3357FF", "#FF33A1", "#A133FF", "#33FFF5", "#F5FF33", "#FF8C33", "#8C33FF", "#33FF8C",
    "#FF3333", "#33FF33", "#3333FF", "#FF33FF", "#33FFFF", "#FFFF33", "#FF6633", "#6633FF", "#33FF66", "#FF3366",
    "#66FF33", "#3366FF", "#FF9933", "#9933FF", "#33FF99", "#FF3399", "#99FF33", "#3399FF", "#FFCC33", "#CC33FF",
    "#33FFCC", "#FF33CC", "#CCFF33", "#33CCFF", "#FF3333", "#33FF33", "#3333FF", "#FF33FF", "#33FFFF", "#FFFF33",
    "#FF6633", "#6633FF", "#33FF66", "#FF3366", "#66FF33", "#3366FF", "#FF9933", "#9933FF", "#33FF99", "#FF3399",
    "#99FF33", "#3399FF", "#FFCC33", "#CC33FF", "#33FFCC", "#FF33CC", "#CCFF33", "#33CCFF"
]

# Global variable to store vessel data
vessel_data_df = pd.DataFrame()

# App layout with improved UI/UX
app.layout = html.Div([
    # Header section
    html.Div([
        html.H1("Real-time Vessel Tracking", style={'textAlign': 'center', 'marginBottom': '10px'}),
        html.Div(id='current-time', style={'fontSize': '16px', 'textAlign': 'center', 'marginBottom': '10px'}),
    ], style={'padding': '10px', 'backgroundColor': '#f8f9fa', 'borderBottom': '1px solid #ddd'}),

    # Main content section
    html.Div([
        # Sidebar - controls
        html.Div([
            html.H3("Controls", style={'textAlign': 'center', 'marginBottom': '20px'}),
            html.Label("Time Range (hours):", style={'fontWeight': 'bold'}),
            dcc.Input(
                id='time-range-input',
                type='number',
                value=1,  # Default to 1 hour
                min=1,
                step=1,
                style={'width': '100%', 'marginBottom': '20px'}
            ),
            html.Label("Source Filter:", style={'fontWeight': 'bold'}),
            dcc.Checklist(
                id='source-filter',
                options=[],  # Dynamically populated
                value=[],  # Default value
                style={'marginBottom': '20px'}
            ),
            html.Div(id='vessel-count', style={'marginTop': '20px', 'fontWeight': 'bold'}),  # Added vessel-count div
            html.Div(id='selected-vessel-info', style={'marginTop': '20px'})
        ], style={
            'width': '15%', 'padding': '20px', 'backgroundColor': '#f8f9fa',
            'borderRight': '1px solid #ddd', 'boxShadow': '2px 0 5px rgba(0,0,0,0.1)', 'height': '100vh', 'overflowY': 'auto'
        }),

        # Main panel - map and details
        html.Div([
            dl.Map(
                [
                    dl.TileLayer(),
                    dl.LayerGroup(id="vessel-tracks"),
                    dl.LayerGroup(id="vessel-markers"),
                    dl.LayerGroup(id="geofence-layer"),
                    dl.LayerGroup(id="trajectory-layer"),
                    dl.FeatureGroup([
                        dl.EditControl(
                            id="draw",
                            position="topright",
                            draw={
                                'rectangle': True,
                                'polygon': True,
                                'circle': False,
                                'circlemarker': False,
                                'marker': False,
                                'polyline': False,
                            },
                        )
                    ])
                ],
                id="map",
                center=MAP_CENTER,
                zoom=MAP_ZOOM,
                style={'width': '100%', 'height': '70vh', 'margin': 'auto', 'display': 'block'},
                zoomControl=True
            ),
            html.Div(id='vessel-details', style={
                'marginTop': '10px',
                'padding': '10px',
                'backgroundColor': '#f0f0f0',
                'borderRadius': '5px',
                'boxShadow': '0 2px 5px rgba(0,0,0,0.1)'
            })
        ], style={'width': '75%', 'display': 'inline-block', 'verticalAlign': 'top', 'padding': '20px'})
    ], style={'display': 'flex'}),

    # Hidden divs for storage
    html.Div(id='geofence-data', style={'display': 'none'}),
    html.Div(id='vessel-data', style={'display': 'none'}),
    html.Div(id='selected-vessel', style={'display': 'none'}),

    # Interval for updating data
    dcc.Interval(
        id='interval-component',
        interval=1*1000,  # 1 second in milliseconds
        n_intervals=0
    )
])

# Function to convert epoch to datetime
def epoch_to_datetime(epoch_time):
    return datetime.fromtimestamp(epoch_time)

# Updated fetch_all_vessel_data function to use user-defined time range
def fetch_all_vessel_data(hours_ago=1):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Calculate timestamp for the user-defined time range
        time_ago = int((datetime.now() - timedelta(hours=hours_ago)).timestamp())

        # Query to fetch all vessel data
        query = """
            SELECT 
                source, vesselname, sourcedatetime, 
                latitude, longitude
            FROM vessel_tracks
            WHERE sourcedatetime >= %s
            ORDER BY sourcedatetime DESC
        """
        params = [time_ago]

        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        data = cursor.fetchall()

        # Check if the query returned any data
        if not data:
            print("No data returned from the database.")
            cursor.close()
            conn.close()
            return pd.DataFrame(columns=columns)  # Return an empty DataFrame with the correct columns

        # Create a DataFrame from the query result
        df = pd.DataFrame(data, columns=columns)

        # Convert sourcedatetime to datetime
        df['timestamp'] = pd.to_datetime(df['sourcedatetime'], unit='s')

        # Calculate speed and course
        df = calculate_speed_and_course(df)

        cursor.close()
        conn.close()

        return df

    except Exception as e:
        print(f"Database error: {e}")
        return pd.DataFrame()

# Updated callback to fetch data based on user-defined time range
@app.callback(
    Output('vessel-data', 'children'),
    [Input('interval-component', 'n_intervals'),
     Input('time-range-input', 'value')]
)
def fetch_and_store_vessel_data(n_intervals, hours_ago):
    global vessel_data_df
    # Fetch the latest data from the database using the user-defined time range
    vessel_data_df = fetch_all_vessel_data(hours_ago)
    return vessel_data_df.to_json(date_format='iso', orient='split')

# Add a callback to dynamically update the source filter options and default values
@app.callback(
    [Output('source-filter', 'options'),
     Output('source-filter', 'value')],  # Set both options and preserve user-selected valuesv
    [Input('interval-component', 'n_intervals')],
    [State('source-filter', 'value')]  # Preserve the current selection
)
def update_source_filter_options(n_intervals, current_selection):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Query to fetch distinct sources
        query = "SELECT DISTINCT source FROM vessel_tracks"
        cursor.execute(query)
        sources = cursor.fetchall()

        # Close the connection
        cursor.close()
        conn.close()

        # Filter out NULL values and convert to the format required by dcc.Checklist
        options = [{'label': source[0], 'value': source[0]} for source in sources if source[0] is not None]
        all_values = [source['value'] for source in options]

        # Preserve the user's current selection, but ensure it only includes valid options
        if current_selection:
            values = [value for value in current_selection if value in all_values]
        else:
            values = all_values  # Default to all options being selected

        return options, values

    except Exception as e:
        print(f"Database error: {e}")
        return [], []

# Callback to filter vessels within the geofence using shapely and checklist
@app.callback(
    [Output('vessel-count', 'children'),
     Output('vessel-details', 'children')],
    [Input('geofence-data', 'children'),
     Input('source-filter', 'value')],
    [State('vessel-data', 'children')]
)
def filter_vessels_within_geofence(geofence_json, selected_sources, vessel_data_json):
    if not geofence_json or not vessel_data_json:
        return "Vessels in view: 0", "Please draw a geofence to view vessel data."

    # Parse geofence and vessel data
    geofence = json.loads(geofence_json)
    df = pd.read_json(vessel_data_json, orient='split')

    if df.empty:
        return "Vessels in view: 0", "No vessel data available."

    # Filter vessels by selected sources
    if selected_sources:
        df = df[df['source'].isin(selected_sources)]

    # Create a shapely polygon from the geofence
    geofence_polygon = Polygon([(lon, lat) for lat, lon in geofence])

    # Filter vessels within the geofence
    df['point'] = df.apply(lambda row: Point(row['longitude'], row['latitude']), axis=1)
    filtered_df = df[df['point'].apply(geofence_polygon.contains)]

    if filtered_df.empty:
        return "Vessels in view: 0", "No vessels in selected area."

    # Get unique vessel count
    unique_vessels = filtered_df['vesselname'].nunique()

    # Get latest positions for all vessels currently plotted on the map
    latest_positions = filtered_df.sort_values('timestamp').groupby('vesselname').last().reset_index()

    # Sort by timestamp with the earliest timing at the top
    latest_positions = latest_positions.sort_values('timestamp', ascending=False).reset_index()

    # Create vessel details display with beautified table
    details = html.Div([
        html.H4("Latest Vessel Positions", style={'textAlign': 'center', 'marginBottom': '20px'}),
        html.Table([
            html.Thead(html.Tr([
                html.Th("Index", style={'padding': '10px', 'border': '1px solid #ddd', 'backgroundColor': '#f2f2f2'}),
                html.Th("Vessel Name", style={'padding': '10px', 'border': '1px solid #ddd', 'backgroundColor': '#f2f2f2'}),
                html.Th("Source", style={'padding': '10px', 'border': '1px solid #ddd', 'backgroundColor': '#f2f2f2'}),
                html.Th("Speed (knots)", style={'padding': '10px', 'border': '1px solid #ddd', 'backgroundColor': '#f2f2f2'}),
                html.Th("Course", style={'padding': '10px', 'border': '1px solid #ddd', 'backgroundColor': '#f2f2f2'}),
                html.Th("Last Update", style={'padding': '10px', 'border': '1px solid #ddd', 'backgroundColor': '#f2f2f2'})
            ])),
            html.Tbody([html.Tr([
                html.Td(_, style={'padding': '10px', 'border': '1px solid #ddd'}),
                html.Td(row['vesselname'], style={'padding': '10px', 'border': '1px solid #ddd'}),
                html.Td(row['source'], style={'padding': '10px', 'border': '1px solid #ddd'}),
                html.Td(f"{row['speed']:.1f}" if not pd.isna(row['speed']) else "N/A", style={'padding': '10px', 'border': '1px solid #ddd'}),
                html.Td(f"{row['course']:.1f}°" if not pd.isna(row['course']) else "N/A", style={'padding': '10px', 'border': '1px solid #ddd'}),
                html.Td(row['timestamp'].strftime('%H:%M:%S'), style={'padding': '10px', 'border': '1px solid #ddd'})
            ]) for _, row in latest_positions.iterrows()
            ])
        ], style={'width': '100%', 'borderCollapse': 'collapse', 'margin': 'auto'})
    ])

    return f"Vessels in view: {unique_vessels}", details

# Function to calculate speed and course between points
def calculate_speed_and_course(df):
    # Sort by time for each vessel
    df = df.sort_values(['vesselname', 'timestamp'])
    
    # Group by vessel
    grouped = df.groupby('vesselname')
    
    # Calculate differences between consecutive points
    df['prev_lat'] = grouped['latitude'].shift(1)
    df['prev_lon'] = grouped['longitude'].shift(1)
    df['prev_time'] = grouped['timestamp'].shift(1)
    
    # Handle vessels with only one data point
    single_point_vessels = grouped.filter(lambda x: len(x) == 1).index
    df.loc[single_point_vessels, 'speed'] = float('nan')  # Set speed to NaN
    df.loc[single_point_vessels, 'course'] = 0  # Set course to 0
    
    # Calculate distance and time differences for other vessels
    mask = ~df['prev_lat'].isna()
    df.loc[mask, 'distance'] = df[mask].apply(
        lambda row: haversine(row['prev_lon'], row['prev_lat'], row['longitude'], row['latitude']), axis=1)
    df.loc[mask, 'time_diff'] = df[mask].apply(
        lambda row: (row['timestamp'] - row['prev_time']).total_seconds(), axis=1)
    
    # Calculate speed (knots) and course
    df.loc[mask, 'speed'] = df[mask].apply(
        lambda row: row['distance'] / (row['time_diff'] / 3600) * 0.539957 if row['time_diff'] > 0 else 0, axis=1)
    df.loc[mask, 'course'] = df[mask].apply(
        lambda row: calculate_initial_compass_bearing(
            (row['prev_lat'], row['prev_lon']),
            (row['latitude'], row['longitude'])
        ), axis=1)
    
    # Drop unnecessary columns
    return df.drop(columns=['prev_lat', 'prev_lon', 'prev_time'])

# Haversine formula to calculate distance between two points
def haversine(lon1, lat1, lon2, lat2):
    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of Earth in kilometers
    return c * r

# Calculate initial compass bearing between two points
def calculate_initial_compass_bearing(pointA, pointB):
    lat1 = math.radians(pointA[0])
    lat2 = math.radians(pointB[0])
    diffLong = math.radians(pointB[1] - pointA[1])
    
    x = math.sin(diffLong) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(diffLong))
    initial_bearing = math.atan2(x, y)
    
    # Convert from radians to degrees
    initial_bearing = math.degrees(initial_bearing)
    
    # Normalize to 0-360
    compass_bearing = (initial_bearing + 360) % 360
    
    return compass_bearing

# Function to assign a color based on the vessel name
def get_vessel_color(vessel_name):
    # Use red for highlighted vessels, blue for others
    if vessel_name in ["VOYAGER 06", "SEAFARER 07"]:
        return "red"
    return "blue"

# Function to create a track as a colored polyline
def create_track_polyline(coordinates, vessel_name):
    return dl.Polyline(
        positions=coordinates,
        color=get_vessel_color(vessel_name),  # Use red or blue based on vessel name
        weight=3,
        opacity=0.7
    )

# Function to create a marker for the last known position with a tooltip
def create_last_position_marker(row):
    tooltip = f"Vessel: {row['vesselname']} | Bearing: {row['course']:.1f}° | Source: {row['source']} | Last Reported: {row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
    return dl.CircleMarker(
        center=(row['latitude'], row['longitude']),
        radius=6,
        color=get_vessel_color(row['vesselname']),  # Use red or blue based on vessel name
        fillColor=get_vessel_color(row['vesselname']),
        fillOpacity=0.8,
        children=[dl.Tooltip(tooltip)],
        id={'type': 'vessel-marker', 'index': row['vesselname']}
    )

# Callback to filter vessels and plot tracks and markers
@app.callback(
    [Output('vessel-tracks', 'children'),
     Output('vessel-markers', 'children')],
    [Input('geofence-data', 'children'),
     Input('source-filter', 'value')],
    [State('vessel-data', 'children')]
)
def update_map_with_tracks_and_markers(geofence_json, selected_sources, vessel_data_json):
    if not geofence_json or not vessel_data_json:
        return [], []

    # Parse geofence and vessel data
    geofence = json.loads(geofence_json)
    df = pd.read_json(vessel_data_json, orient='split')

    if df.empty:
        return [], []

    # Filter vessels by selected sources
    if selected_sources:
        df = df[df['source'].isin(selected_sources)]

    # Create a shapely polygon from the geofence
    geofence_polygon = Polygon([(lon, lat) for lat, lon in geofence])

    # Filter vessels within the geofence
    df['point'] = df.apply(lambda row: Point(row['longitude'], row['latitude']), axis=1)
    filtered_df = df[df['point'].apply(geofence_polygon.contains)]

    if filtered_df.empty:
        return [], []

    # Create tracks and markers for the map
    tracks = []
    markers = []

    for vessel_name, group in filtered_df.groupby('vesselname'):
        # Sort by timestamp
        group = group.sort_values('timestamp')

        # Create track coordinates
        coordinates = list(zip(group['latitude'], group['longitude']))

        # Create track as a polyline
        tracks.append(create_track_polyline(coordinates, vessel_name))

        # Create marker for the last known position
        latest = group.iloc[-1]
        markers.append(create_last_position_marker(latest))

    return tracks, markers

# Function to calculate trajectory
def calculate_trajectory(lat, lon, speed, course, duration_minutes=30):
    # Convert speed from knots to km/h
    speed_kmh = speed * 1.852
    
    # Convert course to radians (0 is north, 90 is east)
    course_rad = (90 - course) * (math.pi / 180)
    
    # Earth's radius in km
    R = 6378.1
    
    # Calculate distance traveled in duration_minutes
    distance = (speed_kmh * (duration_minutes / 60)) / R
    
    # Calculate new position
    new_lat = lat + (distance * math.cos(course_rad)) * (180 / math.pi)
    new_lon = lon + (distance * math.sin(course_rad) / math.cos(lat * (math.pi / 180))) * (180 / math.pi)
    
    return [(lat, lon), (new_lat, new_lon)]

# Callback to update current time
@app.callback(
    Output('current-time', 'children'),
    [Input('interval-component', 'n_intervals')]
)
def update_time(n_intervals):
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return f"Current Time: {current_time}"

# Callback for geofence drawing
@app.callback(
    [Output('geofence-layer', 'children'),
     Output('geofence-data', 'children')],
    [Input('draw', 'geojson')],
    prevent_initial_call=True
)
def handle_geofence(geojson):
    if not geojson:
        raise PreventUpdate

    if 'features' in geojson and len(geojson['features']) > 0:
        feature = geojson['features'][-1]  # Get the last drawn feature
        if feature['geometry']['type'] in ['Polygon', 'Rectangle']:
            coordinates = feature['geometry']['coordinates'][0]
            # Convert coordinates from [lon, lat] to [lat, lon] format
            geofence = [[lat, lon] for lon, lat in coordinates]
            
            # Create polygon layer
            polygon = dl.Polygon(
                positions=geofence,
                color='#3388ff',
                fillColor='#3388ff',
                fillOpacity=0.1,
                weight=2
            )
            
            return [polygon], json.dumps(geofence)

    return dash.no_update, dash.no_update

# Callback for vessel selection and trajectory
@app.callback(
    [Output('selected-vessel-info', 'children'),
     Output('trajectory-layer', 'children'),
     Output('selected-vessel', 'children')],
    [Input({'type': 'vessel-marker', 'index': dash.dependencies.ALL}, 'n_clicks')],
    [State('vessel-data', 'children')]
)
def handle_vessel_selection(clicks, vessel_data_json):
    # Check if there are any clicks or if vessel data is missing
    if not vessel_data_json or not clicks or all(click is None for click in clicks):
        raise PreventUpdate

    # Get the context of the triggered callback
    ctx = dash.callback_context
    if not ctx.triggered or 'index' not in ctx.triggered[0]['prop_id']:
        raise PreventUpdate

    # Extract the vessel name from the triggered marker
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    try:
        vessel_name = json.loads(triggered_id)['index']
    except (KeyError, ValueError):
        raise PreventUpdate

    # Parse vessel data
    df = pd.read_json(vessel_data_json, orient='split')
    vessel_data = df[df['vesselname'] == vessel_name]

    if vessel_data.empty:
        raise PreventUpdate

    # Get the latest vessel information
    latest = vessel_data.sort_values('timestamp').iloc[-1]

    # Create vessel info display
    info = html.Div([
        html.H4(f"Selected Vessel: {latest['vesselname']}"),
        html.P(f"Source: {latest['source']}"),
        html.P(f"Current Speed: {latest['speed']:.1f} knots"),
        html.P(f"Current Course: {latest['course']:.1f}°"),
        html.P(f"Last Update: {latest['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
    ])

    # Calculate and create trajectory
    trajectory = []
    if not pd.isna(latest['speed']) and not pd.isna(latest['course']):
        traj_coords = calculate_trajectory(
            latest['latitude'], latest['longitude'],
            latest['speed'], latest['course']
        )
        trajectory = [dl.Polyline(
            positions=traj_coords,
            color='red',
            weight=2,
            dashArray='10,5',
            opacity=0.7
        )]

    return info, trajectory, latest['vesselname']

if __name__ == '__main__':
    app.run(debug=True)