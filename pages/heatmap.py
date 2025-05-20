import dash
from dash import html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
from utils.database import query_cache, get_all_flights
import traceback
import json

from bokeh.plotting import figure
from bokeh.models import HoverTool, ColorBar, LinearColorMapper, BasicTicker
from bokeh.transform import linear_cmap
from bokeh.palettes import Viridis256, Inferno256, Plasma256, Cividis256, Turbo256
from bokeh.embed import json_item
from bokeh.resources import CDN

# Register the page
dash.register_page(__name__, path="/heatmap")

# Define available color palettes
color_palettes = {
    'Viridis': Viridis256,
    'Inferno': Inferno256,
    'Plasma': Plasma256,
    'Cividis': Cividis256,
    'Turbo': Turbo256
}

def get_heatmap_data():
    """Fetch and process data for heatmap visualization."""
    try:
        # Get flight data from the database
        df = get_all_flights()
        
        if df is None or df.empty or 'longitude' not in df.columns or 'latitude' not in df.columns:
            # Generate dummy data if no real data available
            print("Warning: No valid data for heatmap, using dummy data")
            x = np.random.uniform(-10, 25, 1000)  # Europe-ish longitude range
            y = np.random.uniform(35, 60, 1000)   # Europe-ish latitude range
            # Create some clustering for more interesting heatmap
            for i in range(5):  # Add 5 clusters
                center_x = np.random.uniform(-5, 20)
                center_y = np.random.uniform(40, 55)
                cluster_size = np.random.randint(50, 150)
                x[i*100:i*100+cluster_size] = center_x + np.random.normal(0, 2, cluster_size)
                y[i*100:i*100+cluster_size] = center_y + np.random.normal(0, 2, cluster_size)
        else:
            # Use real data
            print(f"Using flight data with {len(df)} points for heatmap")
            # Get longitude and latitude
            x = df['longitude'].values
            y = df['latitude'].values
        
        # Return as dictionary
        return {
            'longitude': x,
            'latitude': y
        }
    except Exception as e:
        print(f"Error in get_heatmap_data: {str(e)}")
        print(traceback.format_exc())
        # Return empty data if error occurs
        return {'longitude': [], 'latitude': []}

def layout():
    # Get Bokeh resources
    bokeh_js = CDN.js_files[0]  # Main Bokeh JS file
    bokeh_css = CDN.css_files[0]  # Main Bokeh CSS file
    
    return html.Div([
        # Include Bokeh resources
        html.Link(rel="stylesheet", href=bokeh_css),
        html.Script(src=bokeh_js),
        
        html.H1("Heatmap", className="mb-2"),
        html.Div([
            html.H2("Aircraft Density Heatmap"),
            html.Div([
                dbc.Row([
                    dbc.Col([
                        html.Label("Color Palette:"),
                        dcc.Dropdown(
                            id='color-palette-dropdown',
                            options=[{'label': name, 'value': name} for name in color_palettes.keys()],
                            value='Viridis',
                            clearable=False
                        ),
                    ], width=3),
                    dbc.Col([
                        dbc.Button("Refresh Data", id="refresh-heatmap-btn", color="primary", className="mt-4")
                    ], width=3)
                ]),
            ], className="mb-4"),
            html.Div(id="bokeh-heatmap-container", style={"width": "100%", "height": "600px"})
        ], className="p-4 bg-light border rounded")
    ])

@callback(
    Output("bokeh-heatmap-container", "children"),
    [Input("color-palette-dropdown", "value"),
     Input("refresh-heatmap-btn", "n_clicks")]
)
def update_heatmap(palette_name, n_clicks):
    """Update the heatmap with the selected color palette."""
    # Get heatmap data
    data = get_heatmap_data()
    
    # Create the Bokeh figure
    p = create_heatmap_figure(data, palette_name)
    
    # Convert the Bokeh figure to JSON for embedding
    p_json = json.dumps(json_item(p))
    
    # Return the heatmap container with the embedded Bokeh figure
    return html.Div([
        html.Div(id="bokeh-heatmap", style={"width": "100%", "height": "600px"}),
        html.Script(f"""
            document.addEventListener("DOMContentLoaded", function() {{
                const item = {p_json};
                Bokeh.embed.embed_item(item, "bokeh-heatmap");
            }});
        """)
    ])

def create_heatmap_figure(data, palette_name='Viridis'):
    """Create a Bokeh heatmap figure."""
    # Get data as numpy arrays
    x = data['longitude']
    y = data['latitude']
    
    if len(x) == 0 or len(y) == 0:
        # Return an empty figure with a message if no data
        p = figure(
            title="No data available for heatmap",
            height=600,
            width=900,
            toolbar_location="above",
            tools="pan,wheel_zoom,box_zoom,reset,save"
        )
        p.text(0, 0, ["No flight data available"], text_font_size='20pt', text_align='center')
        return p
    
    # Create a 2D histogram
    h, x_edges, y_edges = np.histogram2d(
        x, y, 
        bins=[np.linspace(-15, 35, 100), np.linspace(30, 65, 100)]
    )
    
    # Create the figure with appropriate map tiles
    p = figure(
        title="Aircraft Density Heatmap",
        height=600,
        width=900,
        toolbar_location="above",
        tools="pan,wheel_zoom,box_zoom,reset,save",
        x_axis_label="Longitude",
        y_axis_label="Latitude",
        x_range=(-15, 35),
        y_range=(30, 65),
        match_aspect=True
    )
    
    # Add tile provider for the map background - directly using add_tile
    p.add_tile("CartoDB Positron")
    
    # Get the selected color palette
    palette = color_palettes.get(palette_name, Viridis256)
    
    # Normalize and rescale the histogram data for better visualization
    h_norm = h / np.max(h) if np.max(h) > 0 else h
    
    # Create rectangles for the heatmap with alpha based on value
    dx = (x_edges[1] - x_edges[0])
    dy = (y_edges[1] - y_edges[0])
    
    # Create data source for rectangles
    source_data = {
        'x': [], 'y': [], 'width': [], 'height': [], 'value': []
    }
    
    for i in range(len(x_edges)-1):
        for j in range(len(y_edges)-1):
            if h[i, j] > 0:  # Only add rectangles where there is data
                source_data['x'].append(x_edges[i])
                source_data['y'].append(y_edges[j])
                source_data['width'].append(dx)
                source_data['height'].append(dy)
                source_data['value'].append(h[i, j])
    
    # Create color mapper
    color_mapper = LinearColorMapper(
        palette=palette, 
        low=0, 
        high=np.max(source_data['value']) if source_data['value'] else 1
    )
    
    # Add rectangles to the figure
    p.rect(
        x='x', y='y', width='width', height='height',
        source=source_data,
        fill_color={'field': 'value', 'transform': color_mapper},
        line_color=None,
        alpha=0.7
    )
    
    # Add color bar
    color_bar = ColorBar(
        color_mapper=color_mapper, 
        ticker=BasicTicker(),
        label_standoff=12, 
        border_line_color=None, 
        location=(0, 0),
        title="Aircraft Density"
    )
    p.add_layout(color_bar, 'right')
    
    # Add hover tool
    hover = HoverTool(
        tooltips=[
            ("Longitude", "$x{0.00}"),
            ("Latitude", "$y{0.00}"),
            ("Count", "@value")
        ],
        point_policy="follow_mouse"
    )
    p.add_tools(hover)
    
    return p 