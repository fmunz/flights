import dash
from dash import html, dcc, Output, Input, State, clientside_callback, callback
import dash_bootstrap_components as dbc
import pandas as pd
from utils.database import *
import traceback

import json
from datetime import datetime, timedelta, timezone

# Register the page
dash.register_page(__name__, path="/streaming")

# Define country options function to be called when needed
def get_country_options():
    COUNTRY_COLUMN = 'origin_country'
    countries_df = query_cache("countries")
    unique_countries = countries_df.drop_duplicates(COUNTRY_COLUMN)
    country_options = [
        {"label": row[COUNTRY_COLUMN], "value": row[COUNTRY_COLUMN]}
        for _, row in unique_countries.iterrows() 
        if pd.notnull(row[COUNTRY_COLUMN])
    ]
    return country_options

def layout():
    # Get the UI refresh interval from config (convert seconds to ms)
    ui_refresh_interval_ms = config.get("ui_refresh_interval", 3) * 1000
    return dbc.Container([
        dcc.Location(id="streaming-url", refresh=False),
        
        # Country selector in its own centered, compact card
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("Origin Country", className="mb-0 text-primary")),
                    dbc.CardBody([
                        dcc.Dropdown(
                            id='streaming-country-selector',
                            options=[],  # Will be populated by callback
                            value=None,
                            placeholder="Select Country (optional)",
                            clearable=True,
                            className="mb-0",
                            style={}  # Empty style - will be set by callback
                        )
                    ], className="px-4")
                ], className="shadow-sm mb-3")
            ], width={"size": 4, "offset": 4}, className="text-center")
        ]),
        
        # Store debug info here but don't display visibly
        html.Div(id="debug-info", style={"display": "none"}),
        
        # Main map card
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H4("Live Flight Tracking", className="mb-0")),
                    dbc.CardBody([
                        # Interval for updates
                        dcc.Interval(
                            id="streaming-interval",
                            interval=ui_refresh_interval_ms,  # Use config value
                            n_intervals=0,
                            disabled=True
                        ),
                        
                        # Store for plane data
                        dcc.Store(
                            id="streaming-plane-data",
                            data={"planes": [], "last_refresh": None, "status": "initializing"}
                        ),
                        
                        # The map iframe
                        html.Iframe(
                            id="streaming-map-iframe",
                            src="/static/streaming_map.html",
                            style={
                                "width": "100%",
                                "height": "80vh",  # Responsive height
                                "border": "none",
                                "borderRadius": "8px",
                                "boxShadow": "0 4px 6px rgba(0, 0, 0, 0.1)"
                            },
                            title="Streaming Map"
                        )
                    ], className="p-0")
                ], className="shadow-lg mb-5 bg-white rounded")
            ], width=12)
        ])
    ], fluid=True)

@callback(
    Output("streaming-interval", "disabled"),
    Input("streaming-url", "pathname")
)
def enable_interval(pathname):
    """Enable/disable the update interval based on the current page"""
    return pathname != "/streaming"

@callback(
    Output("streaming-country-selector", "options"),
    Input("streaming-url", "pathname"),
    prevent_initial_call=False
)
def populate_country_options(pathname):
    """Populate the country dropdown when the page loads"""
    if pathname != "/streaming":
        return []  # Empty options if not on this page
    
    options = get_country_options()
    return options

@callback(
    [Output("streaming-plane-data", "data"),
     Output("streaming-map-iframe", "style"),
     Output("streaming-country-selector", "style")],
    [Input("streaming-interval", "n_intervals"),
     Input("streaming-country-selector", "value")],
    prevent_initial_call=True
)
def update_plane_data(n_intervals, selected_country):
    """Update plane data from the database"""
    try:
        # Get current timestamp for performance monitoring
        start_time = datetime.now()
        

        df = get_latest_flights(selected_country)
        #print(f"[Streaming DEBUG] DataFrame dtypes:\n{df.dtypes}")
        #print(f"[Streaming DEBUG] DataFrame columns: {df.columns.tolist()}")
        #print(f"[Streaming DEBUG] First row of data:")
        #print(df.iloc[0].to_dict())

        
        # Check if we got valid data
        if df is None or df.empty:
            # Create an error display component
            error_display = html.Div([
                dbc.Card([
                    dbc.CardHeader(html.H4("Live Map Data Unavailable", className="text-center text-danger")),
                    dbc.CardBody([
                        html.Div([
                            html.I(className="fas fa-exclamation-triangle fa-3x text-danger text-center d-block mb-3"),
                            html.H3("No flight data available", className="text-center text-danger mb-3"),
                            html.P("Please make sure the database is accessible and contains data.", 
                                  className="text-center text-muted mb-4"),
                            html.Hr(),
                            html.H5("Troubleshooting Steps:", className="mt-4 mb-3"),
                            dbc.ListGroup([
                                dbc.ListGroupItem("1. Check your database connection settings in config.yaml"),
                                dbc.ListGroupItem("2. Verify that the Databricks SQL warehouse is running"),
                                dbc.ListGroupItem("3. Ensure the flights tables exist in the specified schema"),
                                dbc.ListGroupItem("4. Check network connectivity to your database")
                            ], className="mb-4"),
                            dbc.Button(
                                "Return to Home", 
                                href="/", 
                                color="primary", 
                                className="d-block mx-auto"
                            )
                        ], className="text-center")
                    ])
                ], className="shadow-lg mt-3")
            ])
            
            # Hide the iframe
            iframe_style = {
                "width": "100%",
                "height": "700px",
                "border": "none",
                "borderRadius": "8px",
                "boxShadow": "0 4px 6px rgba(0, 0, 0, 0.1)",
                "display": "none"  # Hide the iframe
            }
            
            # Hide the country selector
            country_selector_style = {"display": "none"}
            
            error_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            return {
                "planes": [],
                "last_refresh": error_time,
                "status": "error"
            }, None, iframe_style, country_selector_style
            
        # Ensure time_position is a datetime before filtering
        #if 'time_position' in df.columns:
        #    df['time_position'] = pd.to_datetime(df['time_position'], utc=True, errors='coerce')


        old_no_planes = len(df)       
        recent_time_position = df['time_position'].max()
        recent_timestamp = df['ingest_time'].max()

        current_time = datetime.now(timezone.utc)
        ui_time_diff = int((current_time - recent_timestamp).total_seconds())

        # Filter out rows older than x minutes, 2 minutes is the default
        filter_minutes = config.get('filter_old_planes_minutes', 2) 
        df = df[df['time_position'] > (recent_time_position - timedelta(minutes=filter_minutes))]        
        print(f"[Streaming] Time filter removed {old_no_planes - len(df)} rows from {old_no_planes} rows")

        # convert time_position to string before sending 
        df['time_position'] = df['time_position'].dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        planes_data = df.to_dict("records")

        # avoid microseconds in the last refresh time
        ui_last_refresh = current_time.strftime('%Y-%m-%dT%H:%M:%SZ')
        ui_last_data = recent_timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')

        # print(f"[Streaming TIME DEBUG] Time difference: {ui_time_diff}, last refresh: {ui_last_refresh}, last data: {ui_last_data}")



        # Show the iframe
        iframe_style = {
            "width": "100%",
            "height": "700px",
            "border": "none",
            "borderRadius": "8px", 
            "boxShadow": "0 4px 6px rgba(0, 0, 0, 0.1)"
        }
        
        # Style for the country selector
        country_selector_style = {"width": "100%"}
                
        return {
            "planes":        planes_data,
            "last_refresh":  ui_last_refresh,
            "last_data":     ui_last_data,
            "last_time_diff": ui_time_diff,
            "status": "success"
        }, iframe_style, country_selector_style
        
    except Exception as e:
        print(f"[Streaming] Error in update_plane_data: {str(e)}")
        traceback.print_exc()
        error_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Create an error display component
        error_display = html.Div([
            dbc.Card([
                dbc.CardHeader(html.H4("Error Loading Live Map", className="text-center text-danger")),
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-exclamation-circle fa-3x text-danger text-center d-block mb-3"),
                        html.H4("Something went wrong while loading flight data", className="text-center mb-3"),
                        dbc.Alert(
                            f"Error: {str(e)}", 
                            color="danger",
                            className="mb-4"
                        ),
                        dbc.Row([
                            dbc.Col([
                                dbc.Button(
                                    "Return to Home", 
                                    href="/", 
                                    color="secondary", 
                                    className="me-2"
                                ),
                                dbc.Button(
                                    "Try Again", 
                                    href="/streaming", 
                                    color="primary"
                                )
                            ], className="text-center")
                        ])
                    ], className="text-center")
                ])
            ], className="shadow-lg mt-3")
        ])
        
        # Hide the iframe
        iframe_style = {
            "width": "100%",
            "height": "700px",
            "border": "none",
            "borderRadius": "8px",
            "boxShadow": "0 4px 6px rgba(0, 0, 0, 0.1)",
            "display": "none"  # Hide the iframe
        }
        
        # Hide the country selector
        country_selector_style = {"display": "none"}
        
        return {
            "planes": [],
            "last_refresh": error_time,
            "status": "error"
        }, None, iframe_style, country_selector_style

# Clientside callback to update the map
clientside_callback(
    """
    function(data) {
        console.log('[Streaming] Clientside callback triggered:', data);
        
        // Get the iframe
        const iframe = document.getElementById('streaming-map-iframe');
        if (!iframe) {
            console.error('[Streaming] Iframe not found');
            return "Error: iframe not found";
        }
        
        // Check if we have valid data
        if (!data || !data.planes) {
            console.error('[Streaming] Invalid data format:', data);
            return "Error: invalid data";
        }
        
        try {
            // Log the update
            console.log(
                `[Streaming] Sending ${data.planes.length} planes to map at ${data.last_refresh}`
            );
            
            // Send the data to the iframe
            iframe.contentWindow.postMessage(
                {
                    type: 'plane_data',
                    planes: data.planes,
                    ui_last_refresh: data.last_refresh,
                    ui_last_data: data.last_data,
                    ui_time_diff: data.last_time_diff,
                    status: data.status
                },
                '*'
            );
            
            return `Updated: ${data.last_refresh}`;
            
        } catch (error) {
            console.error('[Streaming] Error in clientside callback:', error);
            return `Error: ${error.message}`;
        }
    }
    """,
    Output('streaming-map-iframe', 'title'),
    Input('streaming-plane-data', 'data')
)