import dash_bootstrap_components as dbc
from dash import html, dash_table, register_page
import pandas as pd
from utils.database import query_cache
import traceback

register_page(__name__, path="/airports-table")

def layout():
    try:
        # Fetch data from the on_ground table with hard-coded name
        table_name = "on_ground"
        print(f"Attempting to fetch data from table: {table_name}")  # Debug print
        df = query_cache(table_name)
        print(f"Successfully fetched {len(df)} rows")  # Debug print
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H1("Aircrafts on Ground", className="text-center mb-4"),
                            dash_table.DataTable(
                                id='on-ground-table',
                                columns=[{"name": i, "id": i} for i in df.columns],
                                data=df.to_dict('records'),
                                page_size=10,
                                sort_action='native',
                                style_table={'overflowX': 'auto'},
                                style_cell={
                                    'textAlign': 'left',
                                    'padding': '10px'
                                },
                                style_header={
                                    'backgroundColor': 'rgb(230, 230, 230)',
                                    'fontWeight': 'bold'
                                }
                            )
                        ])
                    ], className="shadow-lg p-4 mb-5 bg-white rounded")
                ])
            ])
        ], fluid=True)
    except Exception as e:
        print(f"Error loading airports table: {str(e)}")
        traceback.print_exc()
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H3("Error Loading Data", className="text-danger"),
                        html.P(f"Error: {str(e)}")
                    ], className="p-5 bg-light border rounded")
                ])
            ])
        ], fluid=True) 