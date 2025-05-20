import dash
from dash import html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
import traceback
import json
import dash_deck
import pydeck as pdk
from utils.database import query_cache, get_all_flights

# Register the page
dash.register_page(__name__, path="/heatmapd")

def get_heatmap_data():
    """Fetch and process data for the heatmap from the data cache."""
    try:
        # Get flight data from the cache
        print("HeatmapD: Getting data from cache")
        df = get_all_flights()
        
        # Print debug info
        print(f"HeatmapD: Retrieved {len(df) if df is not None else 0} rows")
        if df is not None and len(df) > 0:
            print(f"HeatmapD: Columns: {df.columns.tolist()}")
        
        # Check if we have valid data
        if df is None or len(df) == 0 or 'longitude' not in df.columns or 'latitude' not in df.columns:
            print("HeatmapD Warning: No valid data from cache, creating dummy data")
            # Create some dummy data for testing
            lats = np.random.uniform(30, 60, 500)  # Increased number of points
            lons = np.random.uniform(-10, 30, 500)
            # Create a bit of clustering for better visualization
            weights = np.ones(500)
            for i in range(5):  # Add some hotspots
                center_lat = np.random.uniform(35, 55)
                center_lon = np.random.uniform(-5, 25)
                # Add 20 points around each hotspot
                for j in range(20):
                    idx = i * 20 + j
                    if idx < 500:
                        lats[idx] = center_lat + np.random.normal(0, 1)
                        lons[idx] = center_lon + np.random.normal(0, 1)
                        weights[idx] = np.random.uniform(1, 5)  # Higher weights for hotspots
                        
            df = pd.DataFrame({
                'latitude': lats,
                'longitude': lons,
                'weight': weights
            })
        
        # Process dataframe to extract latitude, longitude, and assign weights
        # Keep only valid coordinates and remove any NaN values
        points_df = df[['latitude', 'longitude']].copy()
        points_df = points_df.dropna(subset=['latitude', 'longitude'])
        
        # Filter out any invalid coordinates (sometimes data can have extreme values)
        points_df = points_df[
            (points_df['latitude'] >= -90) & (points_df['latitude'] <= 90) &
            (points_df['longitude'] >= -180) & (points_df['longitude'] <= 180)
        ]
        
        print(f"HeatmapD: After filtering, processed data shape: {points_df.shape}")
        
        # Add weight column (all points have equal weight by default)
        if 'weight' not in points_df.columns:
            points_df['weight'] = 1.0
        
        # Rename columns for deck.gl
        points_df = points_df.rename(columns={
            'latitude': 'lat',
            'longitude': 'lng'
        })
        
        # Sample data if too large (deck.gl can struggle with too many points)
        if len(points_df) > 1000000:
            print(f"HeatmapD: Sampling data from {len(points_df)} to 500000 points")
            points_df = points_df.sample(500000, random_state=42)
        
        return points_df
    except Exception as e:
        print(f"[HeatmapD] Error in get_heatmap_data: {str(e)}")
        print(traceback.format_exc())
        # Return a small dummy dataset in case of error
        print("HeatmapD: Returning dummy data due to error")
        lats = np.random.uniform(30, 60, 100)
        lons = np.random.uniform(-10, 30, 100)
        return pd.DataFrame({
            'lat': lats,
            'lng': lons,
            'weight': np.ones(100)
        })

def create_hexagon_layer(data, intensity=1.0, radius=3000, elevation_scale=20, coverage=0.8, upper_percentile=100, color_range=None):
    """Create a hexagon layer for deck.gl."""
    if color_range is None:
        color_range = [
            [65, 105, 225, 50],     # Royal Blue
            [0, 191, 255, 100],     # Deep Sky Blue  
            [0, 255, 127, 150],     # Spring Green
            [255, 255, 0, 200],     # Yellow
            [255, 165, 0, 225],     # Orange
            [255, 0, 0, 255]        # Red
        ]
    
    return pdk.Layer(
        'HexagonLayer',
        data=data.to_dict('records'),
        get_position=['lng', 'lat'],
        radius=radius,
        elevation_scale=elevation_scale,
        elevation_range=[0, 1000],
        pickable=True,
        extruded=True,
        opacity=intensity,
        upper_percentile=upper_percentile,
        coverage=coverage,
        get_color=[0, 140, 255],
        color_range=color_range
    )

def create_heatmap_layer(data, intensity=1.0, radius=30, threshold=0.03, color_range=None):
    """Create a heatmap layer for deck.gl."""
    if color_range is None:
        color_range = [
            [0, 0, 255],      # Blue
            [0, 255, 255],    # Cyan
            [0, 255, 0],      # Green
            [255, 255, 0],    # Yellow
            [255, 0, 0]       # Red
        ]
    
    return pdk.Layer(
        'HeatmapLayer',
        data=data.to_dict('records'),
        get_position=['lng', 'lat'],
        get_weight='weight',
        aggregation='SUM',
        pickable=True,
        radiusPixels=radius,
        intensity=intensity,
        threshold=threshold,
        color_range=color_range
    )

def create_deck_map(
    data, 
    layer_type="hexagon", 
    intensity=0.8,
    # HexagonLayer params 
    radius=3000, 
    hexagon_elevation_scale=20,
    hexagon_coverage=0.8,
    hexagon_upper_percentile=100,
    # HeatmapLayer params
    heatmap_radius=30,
    heatmap_threshold=0.03,
    # Map view params
    pitch=40,
    bearing=0,
    map_zoom=4
):
    """Create a deck.gl map visualization with the selected layer type."""
    try:
        print(f"HeatmapD: Creating map with {len(data)} data points")
        
        # Ensure we have data with the correct format
        if len(data) == 0 or data is None:
            # Create dummy data for Europe center if no data
            print("HeatmapD: No data available, creating dummy data for visualization")
            dummy_data = pd.DataFrame({
                'lat': [48.0, 46.0, 50.0, 52.0, 49.0],
                'lng': [8.0, 10.0, 6.0, 13.0, 2.0],
                'weight': [1.0, 1.0, 1.0, 1.0, 1.0]
            })
            data = dummy_data
        
        # Calculate center of the data for better viewport
        center_lat = data['lat'].mean()
        center_lng = data['lng'].mean()
        
        # If center calculation fails, use default center
        if pd.isna(center_lat) or pd.isna(center_lng):
            center_lat = 48.0  # Default to central Europe
            center_lng = 10.0
        
        print(f"HeatmapD: Map center at {center_lat}, {center_lng}")
        
        # Limit data size for better performance
        max_points = 10000
        if len(data) > max_points:
            print(f"HeatmapD: Limiting data from {len(data)} to {max_points} points for performance")
            data = data.sample(max_points, random_state=42)
            
        if layer_type == "heatmap":
            layer = create_heatmap_layer(
                data,
                intensity=intensity,
                radius=heatmap_radius,
                threshold=heatmap_threshold
            )
        else:  # default to hexagon
            layer = create_hexagon_layer(
                data,
                intensity,
                radius,
                hexagon_elevation_scale,
                hexagon_coverage,
                hexagon_upper_percentile
            )
        
        # Create a viewport
        view_state = pdk.ViewState(
            latitude=center_lat,
            longitude=center_lng,
            zoom=map_zoom,
            pitch=pitch,
            bearing=bearing
        )
        
        # Create a deck.gl map with map controls enabled
        deck = pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            map_style='light',
            tooltip={
                'html': '<b>Aircraft Count:</b> {colorValue}',
                'style': {
                    'backgroundColor': 'steelblue',
                    'color': 'white'
                }
            }
        )
        
        print(f"HeatmapD: Created deck.gl map with layer type: {layer_type}")
        
        return dash_deck.DeckGL(
            deck.to_json(),
            id="deckgl-map",
            tooltip={"html": "<b>Aircraft Count:</b> {colorValue}"},
            mapboxKey="",  # No key needed for default basemap
            style={"width": "100%", "height": "600px"}  # Ensure map has explicit dimensions
        )
    except Exception as e:
        print(f"HeatmapD Error in create_deck_map: {str(e)}")
        print(traceback.format_exc())
        
        # Fallback to a simple visualization on error
        try:
            # Create a simple scatterplot instead
            view_state = pdk.ViewState(
                latitude=48.0,
                longitude=10.0,
                zoom=map_zoom,
                pitch=0,
                bearing=0
            )
            
            # Sample data to ensure fallback works
            sample_data = data.sample(min(1000, len(data))).to_dict('records') if len(data) > 0 else []
            
            simple_layer = pdk.Layer(
                'ScatterplotLayer',
                data=sample_data,
                get_position=['lng', 'lat'],
                get_radius=50,
                get_fill_color=[0, 0, 255, 100],
                pickable=True
            )
            
            deck = pdk.Deck(
                layers=[simple_layer],
                initial_view_state=view_state,
                map_style='light'
            )
            
            return dash_deck.DeckGL(
                deck.to_json(),
                id="deckgl-map",
                tooltip={"html": "<b>Note:</b> Simplified view due to error"},
                style={"width": "100%", "height": "600px"}
            )
        except:
            # Final fallback if even the simple visualization fails
            return html.Div("Error creating map. See logs for details.", 
                        style={"height": "600px", "display": "flex", "justifyContent": "center", 
                            "alignItems": "center", "color": "red", "border": "1px solid red"})

def layout():
    # Get heatmap data
    print("HeatmapD: Generating layout")
    heatmap_data = get_heatmap_data()
    print(f"HeatmapD: Got data with shape {heatmap_data.shape}")
    
    # Create deck.gl map
    try:
        deck_map = create_deck_map(heatmap_data)
    except Exception as e:
        print(f"HeatmapD Error creating map in layout: {str(e)}")
        print(traceback.format_exc())
        # Provide a fallback UI element if map creation fails
        deck_map = html.Div("Error rendering map. Try refreshing the page or changing settings.",
                          style={"height": "600px", "display": "flex", "justifyContent": "center", 
                                 "alignItems": "center", "color": "red", "border": "1px solid red"})
    
    # Store JSON data
    try:
        heatmap_data_json = heatmap_data.to_json(orient='records')
    except Exception as e:
        print(f"HeatmapD Error converting data to JSON: {str(e)}")
        heatmap_data_json = "[]"  # Empty JSON array as fallback
    
    return html.Div([
        html.H1("Aircraft Density Heatmaps", className="text-center mb-2"),
        
        # Debug information - hidden by default
        html.Div([
            html.Pre(f"Data points: {len(heatmap_data)}")
        ], id="debug-info", style={'display': 'none', "padding": "10px", "background": "#f8f9fa", "border": "1px solid #ddd"}),
        
        dbc.Row([
            # Controls in a sidebar
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Layer Settings"),
                    dbc.CardBody([
                        html.Label("Layer Type:"),
                        dcc.Dropdown(
                            id='layer-type-dropdown',
                            options=[
                                {'label': 'Hexagon', 'value': 'hexagon'},
                                {'label': 'Heatmap', 'value': 'heatmap'}
                            ],
                            value='hexagon',
                            className="mb-3"
                        ),
                        
                        # Common settings
                        html.Label("Intensity:"),
                        dcc.Slider(
                            id='intensity-slider',
                            min=0.1,
                            max=1.0,
                            step=0.1,
                            value=0.8,
                            marks={i/10: str(i/10) for i in range(1, 11)},
                            className="mb-3"
                        ),
                        
                        # Map navigation info
                        html.Div([
                            html.I(className="fas fa-info-circle mr-2"),
                            html.Span("Use Shift+Mouse to navigate, rotate and zoom the map", 
                                     style={"font-style": "italic", "color": "#6c757d"})
                        ], className="mb-3 mt-2 d-flex align-items-center")
                    ])
                ], className="mb-3"),
                
                # Hexagon Layer Settings Card
                dbc.Card([
                    dbc.CardHeader("Hexagon Layer Settings"),
                    dbc.CardBody([
                        html.Label("Radius:"),
                        dcc.Slider(
                            id='hexagon-radius-slider',
                            min=1000,
                            max=10000,
                            step=1000,
                            value=3000,
                            marks={i: f"{i//1000}km" for i in range(1000, 11000, 1000)},
                            className="mb-3"
                        ),
                        html.Label("Elevation Scale:"),
                        dcc.Slider(
                            id='hexagon-elevation-slider',
                            min=0,
                            max=50,
                            step=5,
                            value=20,
                            marks={i: str(i) for i in range(0, 51, 10)},
                            className="mb-3"
                        ),
                        html.Label("Coverage:"),
                        dcc.Slider(
                            id='hexagon-coverage-slider',
                            min=0.1,
                            max=1.0,
                            step=0.1,
                            value=0.8,
                            marks={i/10: str(i/10) for i in range(1, 11)},
                            className="mb-3"
                        ),
                        html.Label("Upper Percentile:"),
                        dcc.Slider(
                            id='hexagon-percentile-slider',
                            min=80,
                            max=100,
                            step=5,
                            value=100,
                            marks={i: f"{i}%" for i in range(80, 101, 5)},
                            className="mb-3"
                        ),
                    ])
                ], id="hexagon-settings", style={'display': 'block'}, className="mb-3"),
                
                # Heatmap Layer Settings Card
                dbc.Card([
                    dbc.CardHeader("Heatmap Layer Settings"),
                    dbc.CardBody([
                        html.Label("Radius (pixels):"),
                        dcc.Slider(
                            id='heatmap-radius-slider',
                            min=10,
                            max=100,
                            step=10,
                            value=30,
                            marks={i: str(i) for i in range(10, 101, 10)},
                            className="mb-3"
                        ),
                        html.Label("Threshold:"),
                        dcc.Slider(
                            id='heatmap-threshold-slider',
                            min=0.01,
                            max=0.1,
                            step=0.01,
                            value=0.03,
                            marks={i/100: str(i/100) for i in range(1, 11)},
                            className="mb-3"
                        ),
                    ])
                ], id="heatmap-settings", style={'display': 'none'}, className="mb-3"),
                
                # Buttons
                dbc.Button(
                    "Refresh Data",
                    id="refresh-btn",
                    color="primary",
                    className="mb-3 w-100"
                ),
                
                # Add a debug button
                dbc.Button(
                    "Toggle Debug Info",
                    id="debug-btn",
                    color="secondary",
                    className="mb-3 w-100"
                )
            ], width=3),
            
            # Map column
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Aircraft Density Map"),
                    dbc.CardBody([
                        # Deck.gl map container
                        html.Div([
                            deck_map
                        ], style={
                            'height': '650px',
                            'width': '100%',
                            'position': 'relative',
                            'borderRadius': '8px',
                            'overflow': 'hidden',
                        }, id="map-container")
                    ])
                ])
            ], width=9)
        ]),
        
        # Store the data
        dcc.Store(id='heatmap-data', data=heatmap_data_json),
        
        # Load notification
        dcc.Loading(
            id="loading-map",
            type="circle",
            children=html.Div(id="loading-output")
        )
    ])

# Callbacks
@callback(
    [Output('hexagon-settings', 'style'),
     Output('heatmap-settings', 'style')],
    [Input('layer-type-dropdown', 'value')]
)
def toggle_layer_settings(layer_type):
    """Show or hide layer-specific settings based on selected layer type."""
    hexagon_style = {'display': 'block' if layer_type == 'hexagon' else 'none'}
    heatmap_style = {'display': 'block' if layer_type == 'heatmap' else 'none'}
    
    return hexagon_style, heatmap_style

@callback(
    [Output('deckgl-map', 'data'),
     Output('loading-output', 'children')],
    [Input('layer-type-dropdown', 'value'),
     Input('intensity-slider', 'value'),
     # Hexagon layer inputs
     Input('hexagon-radius-slider', 'value'),
     Input('hexagon-elevation-slider', 'value'),
     Input('hexagon-coverage-slider', 'value'),
     Input('hexagon-percentile-slider', 'value'),
     # Heatmap layer inputs
     Input('heatmap-radius-slider', 'value'),
     Input('heatmap-threshold-slider', 'value'),
     # Refresh button
     Input('refresh-btn', 'n_clicks')],
    [State('heatmap-data', 'data')],
    prevent_initial_call=False
)
def update_deck_map(
    layer_type,
    intensity,
    hexagon_radius,
    hexagon_elevation,
    hexagon_coverage,
    hexagon_percentile,
    heatmap_radius,
    heatmap_threshold,
    n_clicks,
    data_json
):
    """Update the deck.gl map based on selected parameters."""
    try:
        trigger_id = dash.callback_context.triggered[0]['prop_id'].split('.')[0] if dash.callback_context.triggered else None
        print(f"HeatmapD: Updating deck map with layer type: {layer_type}, trigger: {trigger_id}")
        
        # Default values for map view settings
        pitch = 40
        bearing = 0
        zoom = 4
        
        # Get current data or refresh if refresh button was clicked
        if trigger_id == 'refresh-btn':
            print("HeatmapD: Refreshing data from cache")
            data = get_heatmap_data()
            status = "Data refreshed from cache"
        else:
            # Parse the JSON back to a DataFrame
            try:
                if data_json and data_json != "[]":
                    data = pd.read_json(data_json, orient='records')
                    status = f"Using cached data ({len(data)} points)"
                else:
                    print("HeatmapD: Empty data in store, fetching new data")
                    data = get_heatmap_data()
                    status = "Initial data loaded"
            except Exception as e:
                print(f"HeatmapD Error parsing JSON data: {str(e)}")
                print(traceback.format_exc())
                data = pd.DataFrame(columns=['lat', 'lng', 'weight'])
                status = "Error loading data"
        
        print(f"HeatmapD: Updating map with {len(data)} data points")
        
        # Create updated deck.gl map with performance limits applied in the create_deck_map function
        deck = create_deck_map(
            data,
            layer_type=layer_type,
            intensity=intensity,
            # Map view params
            pitch=pitch,
            bearing=bearing,
            map_zoom=zoom,
            # HexagonLayer params
            radius=hexagon_radius,
            hexagon_elevation_scale=hexagon_elevation,
            hexagon_coverage=hexagon_coverage,
            hexagon_upper_percentile=hexagon_percentile,
            # HeatmapLayer params
            heatmap_radius=heatmap_radius,
            heatmap_threshold=heatmap_threshold
        )
        
        return deck.data, status
    except Exception as e:
        print(f"HeatmapD Error updating deck map: {str(e)}")
        print(traceback.format_exc())
        
        # Return an empty map in case of error
        try:
            # Simple fallback map
            default_view_state = pdk.ViewState(
                latitude=48.0,
                longitude=10.0,
                zoom=zoom,
                pitch=0,
                bearing=0
            )
            
            empty_deck = pdk.Deck(
                layers=[],
                initial_view_state=default_view_state,
                map_style='light',
                controller=True
            )
            
            empty_deck_gl = dash_deck.DeckGL(
                empty_deck.to_json(),
                id="deckgl-map",
                tooltip={"html": f"<b>Error:</b> {str(e)[:50]}..."}
            )
            
            return empty_deck_gl.data, f"Error: {str(e)[:100]}"
        except:
            # If even the empty map fails
            return {}, f"Critical error: Unable to create map"

@callback(
    Output("debug-info", "style"),
    Input("debug-btn", "n_clicks"),
    State("debug-info", "style"),
    prevent_initial_call=True
)
def toggle_debug_info(n_clicks, current_style):
    """Toggle the display of debug information."""
    if current_style["display"] == "none":
        return {"display": "block", "padding": "10px", "background": "#f8f9fa", "border": "1px solid #ddd"}
    else:
        return {"display": "none"} 