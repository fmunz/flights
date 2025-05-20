import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from utils.database import query_cache
import pycountry

# Register this page
dash.register_page(__name__, path="/statistics")

def get_stats_data():
    """Get statistics data from the database with automatic caching"""
    # Get the last timestamp data (database status)
    last_timestamp_df = query_cache("last_timestamp")
    return last_timestamp_df

def layout():
    """Build the statistics page layout"""
    # The layout now has static content triggered just once when the page loads
    return dbc.Container([
        dcc.Location(id="statistics-url", refresh=False),
        
        # Content container - will be populated once when page loads
        html.Div(id="statistics-content"),
        
    ], fluid=True)

@callback(
    Output("statistics-content", "children"),
    Input("statistics-url", "pathname"),
)
def update_statistics_content(pathname):
    """Update statistics content when page loads or URL changes"""
    if pathname != "/statistics":
        return html.Div()
    
    try:
        start_time = datetime.now()
        
        # Get statistics data - caching logic handled in query_cache
        last_timestamp_df = get_stats_data()
        
        # Check if we have valid data
        if last_timestamp_df is None or last_timestamp_df.empty:
            return html.Div([
                dbc.Container([
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader(html.H4("Flight Statistics Dashboard", className="text-center mb-2")),
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
                            ], className="shadow-lg mt-5")
                        ], width={"size": 8, "offset": 2})
                    ])
                ], fluid=True)
            ])
        
        else:
            # Calculate query time
            query_time = (datetime.now() - start_time).total_seconds()
            
            # Process the flight data for visualization
            try:
                # Create a copy to avoid modifying the cached dataframe
                processed_df = last_timestamp_df.copy()
                
                # Direct assignments based on known column names
                altitude_col = 'geo_altitude'
                velocity_col = 'velocity'
                origin_country_col = 'origin_country'
                vertical_rate_col = 'vertical_rate'
                callsign_col = 'callsign'
                
                # Categorize flight phases
                def categorize_phase(row):
                    # First check if the flight is on ground
                    if row['on_ground'] == True:
                        return 'On Ground'
                    
                    # Check if we have vertical rate info for more precise categorization
                    if vertical_rate_col in processed_df.columns and vertical_rate_col in row and not pd.isna(row[vertical_rate_col]):
                        vrate = row[vertical_rate_col]
                        if vrate > 2.5:
                            return 'Ascending'
                        elif vrate < -2.5:
                            return 'Descending'
                    
                    # If not climbing or descending, it's cruising
                    return 'Cruising'
                
                # Apply the categorization
                processed_df['flight_phase'] = processed_df.apply(categorize_phase, axis=1)
                
                # Count flights by phase
                phase_counts = processed_df['flight_phase'].value_counts().reset_index()
                phase_counts.columns = ['Flight Phase', 'Count']
                
                # Get total flights
                total_flights = len(processed_df)
                
                # Calculate flight status metrics
                status_counts = processed_df['flight_phase'].value_counts()
                total_aircraft = len(processed_df)
                on_ground = status_counts.get('On Ground', 0)
                in_air = total_aircraft - on_ground
                ascending = status_counts.get('Ascending', 0)
                descending = status_counts.get('Descending', 0)
                cruising = status_counts.get('Cruising', 0)
                
                # ---- Create the 4 visualizations ----
                
                # 1. Flight phases donut chart
                status_colors = {
                    'Ascending': '#4CAF50',
                    'Cruising': '#2196F3',
                    'Descending': '#FF9800',
                    'On Ground': '#F44336'
                }
                
                donut_fig = go.Figure(go.Pie(
                    labels=status_counts.index,
                    values=status_counts.values,
                    marker=dict(colors=[status_colors.get(cat, '#999999') for cat in status_counts.index]),
                    hole=0.6,
                    textinfo='label+percent',
                    insidetextorientation='radial',
                ))
                donut_fig.update_layout(
                    title=dict(text='Flight Status Distribution', font=dict(size=18), x=0.5),
                    showlegend=False,
                    margin=dict(t=60, b=0, l=0, r=0),
                    annotations=[dict(text=f"Total: {total_aircraft}", x=0.5, y=0.5, font_size=14, showarrow=False)]
                )
                
                # 2. Altitude histogram
                alt_fig = go.Figure()
                if altitude_col in processed_df.columns:
                    altitude_data = processed_df[~processed_df.get('on_ground', False)][altitude_col].dropna()
                    if len(altitude_data) > 0:
                        alt_fig = px.histogram(altitude_data, nbins=50, opacity=0.7, 
                                              color_discrete_sequence=['#2196F3'])
                        mean_altitude = altitude_data.mean()
                        alt_fig.add_vline(x=mean_altitude, line_dash='dash', line_color='red')
                        
                        y_data = alt_fig.data[0]['y'] if alt_fig.data and 'y' in alt_fig.data[0] else None
                        if y_data is not None and len(y_data) > 0:
                            alt_fig.add_annotation(x=mean_altitude, y=max(y_data),
                                text=f"Mean: {mean_altitude:.0f} m", showarrow=False, yshift=20, font=dict(color='red'))
                        
                        alt_fig.update_layout(
                            title=dict(text='Altitude Distribution', font=dict(size=18), x=0.5),
                            xaxis_title=f'Altitude ({altitude_col}) in meters',
                            yaxis_title='Number of Aircraft',
                            margin=dict(t=60, b=40, l=0, r=0),
                            xaxis=dict(range=[0, 15000])
                        )
                    else:
                        alt_fig.add_annotation(text='No airborne altitude data available', x=0.5, y=0.5, showarrow=False)
                else:
                    alt_fig.add_annotation(text='Altitude data not available', x=0.5, y=0.5, showarrow=False)
                
                # 3. Speed histogram
                speed_fig = go.Figure()
                if velocity_col in processed_df.columns:
                    velocity_data = processed_df[~processed_df.get('on_ground', False)][velocity_col].dropna()
                    if len(velocity_data) > 0:
                        speed_fig = px.histogram(velocity_data, nbins=50, opacity=0.7,
                                                color_discrete_sequence=['#4CAF50'])
                        mean_velocity = velocity_data.mean()
                        speed_fig.add_vline(x=mean_velocity, line_dash='dash', line_color='red')
                        
                        y_data = speed_fig.data[0]['y'] if speed_fig.data and 'y' in speed_fig.data[0] else None
                        if y_data is not None and len(y_data) > 0:
                            speed_fig.add_annotation(x=mean_velocity, y=max(y_data),
                                text=f"Mean: {mean_velocity:.1f} m/s", showarrow=False, yshift=20, font=dict(color='red'))
                        
                        speed_fig.update_layout(
                            title=dict(text='Speed Distribution', font=dict(size=18), x=0.5),
                            xaxis_title=f'Speed ({velocity_col}) in m/s',
                            yaxis_title='Number of Aircraft',
                            margin=dict(t=60, b=40, l=0, r=0),
                            xaxis=dict(range=[0, 350])
                        )
                    else:
                        speed_fig.add_annotation(text='No airborne velocity data available', x=0.5, y=0.5, showarrow=False)
                else:
                    speed_fig.add_annotation(text='Velocity data not available', x=0.5, y=0.5, showarrow=False)
                
                # 4. Country histogram
                country_fig = go.Figure()
                if origin_country_col in processed_df.columns:
                    country_counts = processed_df[origin_country_col].value_counts().head(15)
                    if len(country_counts) > 0:
                        country_fig = go.Figure(go.Bar(
                            y=country_counts.index[::-1],
                            x=country_counts.values[::-1],
                            orientation='h',
                            marker_color='#FF9800',
                            text=country_counts.values[::-1],
                            textposition='auto'
                        ))
                        country_fig.update_layout(
                            title=dict(text='Top Flight Origin Countries', font=dict(size=18), x=0.5),
                            xaxis_title='Number of Aircraft',
                            yaxis_title='',
                            margin=dict(t=60, b=40, l=0, r=0)
                        )
                    else:
                        country_fig.add_annotation(text='No country data available', x=0.5, y=0.5, showarrow=False)
                else:
                    country_fig.add_annotation(text='Country data not available', x=0.5, y=0.5, showarrow=False)
                
                # Create stats table
                stats_df = pd.DataFrame({
                    'Metric': [
                        'Total Aircraft',
                        'Aircraft in Air',
                        'Aircraft on Ground',
                        'Ascending',
                        'Cruising', 
                        'Descending'
                    ],
                    'Count': [
                        total_aircraft,
                        in_air,
                        on_ground,
                        ascending,
                        cruising,
                        descending
                    ],
                    'Percentage': [
                        '100%',
                        f'{in_air/total_aircraft*100:.1f}%' if total_aircraft > 0 else 'N/A',
                        f'{on_ground/total_aircraft*100:.1f}%' if total_aircraft > 0 else 'N/A',
                        f'{ascending/in_air*100:.1f}%' if in_air > 0 else 'N/A',
                        f'{cruising/in_air*100:.1f}%' if in_air > 0 else 'N/A',
                        f'{descending/in_air*100:.1f}%' if in_air > 0 else 'N/A'
                    ]
                })
                
                # Find records (fastest, highest aircraft)
                records_table_rows = []
                
                # Filter out planes on ground
                airborne_df = processed_df[~processed_df.get('on_ground', False)]
                
                # Only proceed if we have airborne planes
                if not airborne_df.empty and callsign_col in processed_df.columns and origin_country_col in processed_df.columns:
                    # Get fastest plane
                    if velocity_col in processed_df.columns:
                        fastest_idx = airborne_df[velocity_col].idxmax()
                        if fastest_idx is not None:
                            fastest_plane = airborne_df.loc[fastest_idx]
                            fastest_callsign = fastest_plane.get(callsign_col, 'N/A')
                            fastest_speed = fastest_plane.get(velocity_col, 'N/A')
                            fastest_country = fastest_plane.get(origin_country_col, 'N/A')
                            country_flag = get_country_flag_emoji(fastest_country)
                            records_table_rows.append({
                                'Category': 'Fastest Plane',
                                'Callsign': f"{country_flag} {fastest_callsign}",
                                'Value': f"{fastest_speed * 3.6:.1f} km/h" if isinstance(fastest_speed, (int, float)) else fastest_speed,
                                'Country': fastest_country
                            })
                    
                    # Get highest plane
                    if altitude_col in processed_df.columns:
                        highest_idx = airborne_df[altitude_col].idxmax()
                        if highest_idx is not None:
                            highest_plane = airborne_df.loc[highest_idx]
                            highest_callsign = highest_plane.get(callsign_col, 'N/A')
                            highest_altitude = highest_plane.get(altitude_col, 'N/A')
                            highest_country = highest_plane.get(origin_country_col, 'N/A')
                            country_flag = get_country_flag_emoji(highest_country)
                            records_table_rows.append({
                                'Category': 'Highest Plane',
                                'Callsign': f"{country_flag} {highest_callsign}",
                                'Value': f"{highest_altitude:.1f} m" if isinstance(highest_altitude, (int, float)) else highest_altitude,
                                'Country': highest_country
                            })
                    
                    # Get highest ascent rate
                    if vertical_rate_col in processed_df.columns:
                        highest_ascent_idx = airborne_df[vertical_rate_col].idxmax()
                        if highest_ascent_idx is not None:
                            ascent_plane = airborne_df.loc[highest_ascent_idx]
                            ascent_callsign = ascent_plane.get(callsign_col, 'N/A')
                            ascent_rate = ascent_plane.get(vertical_rate_col, 'N/A')
                            ascent_country = ascent_plane.get(origin_country_col, 'N/A')
                            country_flag = get_country_flag_emoji(ascent_country)
                            records_table_rows.append({
                                'Category': 'Max Climb Rate',
                                'Callsign': f"{country_flag} {ascent_callsign}",
                                'Value': f"{ascent_rate:.1f} m/s" if isinstance(ascent_rate, (int, float)) else ascent_rate,
                                'Country': ascent_country
                            })
                        
                        # Get highest descent rate
                        highest_descent_idx = airborne_df[vertical_rate_col].idxmin()
                        if highest_descent_idx is not None:
                            descent_plane = airborne_df.loc[highest_descent_idx]
                            descent_callsign = descent_plane.get(callsign_col, 'N/A')
                            descent_rate = descent_plane.get(vertical_rate_col, 'N/A')
                            descent_country = descent_plane.get(origin_country_col, 'N/A')
                            country_flag = get_country_flag_emoji(descent_country)
                            records_table_rows.append({
                                'Category': 'Max Descent Rate',
                                'Callsign': f"{country_flag} {descent_callsign}",
                                'Value': f"{descent_rate:.1f} m/s" if isinstance(descent_rate, (int, float)) else descent_rate,
                                'Country': descent_country
                            })
                
                records_df = pd.DataFrame(records_table_rows) if records_table_rows else pd.DataFrame({
                    'Category': ['No Data Available'],
                    'Callsign': [''],
                    'Value': [''],
                    'Country': ['']
                })
                
                # Create the content with all 4 diagrams
                content = dbc.Container([
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader(html.H4("Flight Statistics Dashboard")),
                                dbc.CardBody([
                                    # Tables for stats and records
                                    dbc.Row([
                                        dbc.Col([
                                            html.H5("Flight Statistics Summary", className="mb-3 fw-bold"),
                                            dbc.Table.from_dataframe(stats_df, striped=True, bordered=True, hover=True, 
                                                                className="bg-white table-sm mb-4")
                                        ], width=6),
                                        dbc.Col([
                                            html.H5("Notable Aircraft Records", className="mb-3 fw-bold"),
                                            dbc.Table.from_dataframe(
                                                records_df,
                                                striped=True, bordered=True, hover=True, 
                                                className="bg-white table-sm mb-4"
                                            )
                                        ], width=6)
                                    ]),
                                    
                                    # First row of charts
                                    dbc.Row([
                                        dbc.Col(dcc.Graph(figure=donut_fig), width=6),
                                        dbc.Col(dcc.Graph(figure=country_fig), width=6),
                                    ]),
                                    
                                    # Second row of charts
                                    dbc.Row([
                                        dbc.Col(dcc.Graph(figure=alt_fig), width=6),
                                        dbc.Col(dcc.Graph(figure=speed_fig), width=6)
                                    ])
                                ])
                            ], className="shadow-lg mb-5")
                        ], width=12)
                    ])
                ], fluid=True)
                
                return content
            
            except Exception as e:
                error_content = html.Div([
                    dbc.Container([
                        dbc.Row([
                            dbc.Col([
                                dbc.Card([
                                    dbc.CardHeader(html.H4("Error Processing Flight Data", className="text-center text-danger")),
                                    dbc.CardBody([
                                        html.Div([
                                            html.I(className="fas fa-exclamation-circle fa-3x text-danger text-center d-block mb-3"),
                                            html.H4("Something went wrong while processing flight data", className="text-center mb-3"),
                                            dbc.Alert(
                                                f"Error: {str(e)}", 
                                                color="danger",
                                                className="mb-4"
                                            ),
                                            dbc.Card([
                                                dbc.CardHeader("Technical Details"),
                                                dbc.CardBody([
                                                    html.Pre(str(e), className="bg-light p-3 rounded small")
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
                                                        href="/statistics", 
                                                        color="primary"
                                                    )
                                                ], className="text-center")
                                            ])
                                        ], className="text-center")
                                    ])
                                ], className="shadow-lg mt-5")
                            ], width={"size": 10, "offset": 1})
                        ])
                    ], fluid=True)
                ])
                return error_content
    
    except Exception as e:
        return html.Div([
            dbc.Container([
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader(html.H4("Error Loading Statistics", className="text-center text-danger")),
                            dbc.CardBody([
                                html.Div([
                                    html.I(className="fas fa-bug fa-3x text-danger text-center d-block mb-3"),
                                    html.H4("Unable to load statistics page", className="text-center mb-3"),
                                    dbc.Alert(
                                        f"Error: {str(e)}", 
                                        color="danger",
                                        className="mb-4"
                                    ),
                                    dbc.Button(
                                        "Return to Home", 
                                        href="/", 
                                        color="primary", 
                                        className="d-block mx-auto"
                                    )
                                ], className="text-center")
                            ])
                        ], className="shadow-lg mt-5")
                    ], width={"size": 8, "offset": 2})
                ])
            ], fluid=True)
        ])

def get_country_flag_emoji(country_name):
    """Convert country name to emoji flag"""
    try:
        if not country_name or pd.isna(country_name) or country_name == "":
            return "🏳️"
            
        # Some common mappings for problematic country names
        country_mappings = {
            "United States": "US",
            "Russia": "RU",
            "UK": "GB",
            "United Kingdom": "GB",
            "UAE": "AE",
            "Vietnam": "VN",
            "Laos": "LA",
            "South Korea": "KR",
            "North Korea": "KP",
            "Taiwan": "TW"
        }
        
        if country_name in country_mappings:
            country_code = country_mappings[country_name]
        else:
            # Try to find the country by name
            country = pycountry.countries.get(name=country_name)
            if not country:
                # Try to search by fuzzy matching
                countries = pycountry.countries.search_fuzzy(country_name)
                country = countries[0] if countries else None
                
            country_code = country.alpha_2 if country else "XX"
        
        # Convert country code to emoji flag
        flag = ''.join(chr(ord(c) + 127397) for c in country_code)
        return flag
    except Exception:
        return "🏳️" 