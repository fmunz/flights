import dash_bootstrap_components as dbc
from dash import html, register_page, dcc, Input, Output, callback, no_update
import pandas as pd
import plotly.graph_objects as go
from utils.database import query_cache, get_all_flights
import traceback
import plotly.express as px

register_page(__name__, path="/flight-map")
register_page(__name__, path="/map")  # Also register under /map for compatibility

# Get country options directly from database cache
countries_df = query_cache("countries")
COUNTRY_COLUMN = 'origin_country'
country_options = []

try:
    if COUNTRY_COLUMN in countries_df.columns:
        unique_countries = countries_df.drop_duplicates(COUNTRY_COLUMN)
        country_options = [
            {"label": row[COUNTRY_COLUMN], "value": row[COUNTRY_COLUMN]}
            for _, row in unique_countries.iterrows()
        ]
except Exception as e:
    print(f"Error loading country options: {e}")
    country_options = []  # Default empty list

# Add "All Countries" option
country_options = [{"label": "All Countries", "value": "ALL"}] + country_options

def layout():
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H1("Flight Tracking Map", className="text-center mb-2"),
                html.Div([
                    html.Label("Select Country:"),
                    dcc.Dropdown(
                        id="country-selector",
                        options=country_options,
                        value="ALL",
                        className="mb-3"
                    ),
                    html.Div(
                        id="loading-map",
                        children=dcc.Graph(id="flight-map", style={"height": "80vh"})
                    )
                ])
            ])
        ])
    ], fluid=True)

@callback(
    [Output("flight-map", "figure"),
     Output("loading-map", "children")],
    [Input("country-selector", "value")]
)
def update_map(selected_country):
    try:
        # Get flight data using the get_all_flights function
        df = get_all_flights()
        
        # Check if we got valid data
        if df is None or df.empty:
            # Return both outputs: empty figure and error display
            empty_fig = px.scatter_geo()
            empty_fig.update_layout(height=800, margin=dict(l=0, r=0, t=30, b=0))
            
            error_display = html.Div([
                dcc.Graph(id="flight-map", figure=empty_fig, style={"height": "80vh", "display": "none"}),
                dbc.Card([
                    dbc.CardHeader(html.H4("Flight Map Data Unavailable", className="text-center text-danger")),
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
                ], className="shadow-lg")
            ])
            
            return empty_fig, error_display
        
        # Filter by country if a specific country is selected
        if selected_country and selected_country != "ALL":
            df = df[df[COUNTRY_COLUMN] == selected_country]
        
        # Create the map figure
        fig = go.Figure()
        
        # Add flight points
        fig.add_trace(go.Scattergeo(
            lon=df["longitude"],
            lat=df["latitude"],
            text=df["callsign"],
            mode="markers",
            marker=dict(
                size=6,
                color="red",
                symbol="triangle-up",
                opacity=0.7
            ),
            hovertemplate=(
                "<b>%{text}</b><br>" +
                "Altitude: %{customdata[0]} ft<br>" +
                "Velocity: %{customdata[1]} knots<br>" +
                "Country: %{customdata[2]}<br>" +
                "ICAO24: %{customdata[3]}<br>" +
                "<extra></extra>"
            ),
            customdata=df[["altitude", "velocity", COUNTRY_COLUMN, "icao24"]].values
        ))
        
        # Update the layout
        fig.update_layout(
            title=f"Flight Tracking - {'All Countries' if selected_country == 'ALL' else selected_country}",
            geo=dict(
                projection_type="natural earth",
                showland=True,
                landcolor="rgb(243, 243, 243)",
                countrycolor="rgb(204, 204, 204)",
                showocean=True,
                oceancolor="rgb(230, 245, 254)"
            ),
            height=800,
            margin=dict(l=0, r=0, t=30, b=0)
        )
        
        # Return the figure and keep the current children
        return fig, no_update
        
    except Exception as e:
        print(f"Error updating map: {e}")
        traceback.print_exc()
        
        # Return both outputs: empty figure and error display
        empty_fig = px.scatter_geo()
        empty_fig.update_layout(height=800, margin=dict(l=0, r=0, t=30, b=0))
        
        error_display = html.Div([
            dcc.Graph(id="flight-map", figure=empty_fig, style={"height": "80vh", "display": "none"}),
            dbc.Card([
                dbc.CardHeader(html.H4("Error Loading Flight Map", className="text-center text-danger")),
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-exclamation-circle fa-3x text-danger text-center d-block mb-3"),
                        html.H4("Something went wrong while loading flight data", className="text-center mb-3"),
                        dbc.Alert(
                            f"Error: {str(e)}", 
                            color="danger",
                            className="mb-4"
                        ),
                        dbc.Card([
                            dbc.CardHeader("Technical Details"),
                            dbc.CardBody([
                                html.Pre(traceback.format_exc(), className="bg-light p-3 rounded small")
                            ])
                        ], className="mb-4"),
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
                                    href="/flight-map", 
                                    color="primary"
                                )
                            ], className="text-center")
                        ])
                    ], className="text-center")
                ])
            ], className="shadow-lg")
        ])
        
        return empty_fig, error_display 