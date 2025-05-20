import dash
from dash import html, dcc, Output, Input, register_page, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
from utils.database import query_cache
import traceback

register_page(__name__, path="/on_ground")

def layout():
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H1("Aircraft Currently on Ground", className="text-center mb-2"),
                dcc.Loading(
                    id="loading-on-ground",
                    type="circle",
                    children=html.Div(id="on-ground-container")
                )
            ])
        ])
    ], fluid=True)

@dash.callback(
    Output("on-ground-container", "children"),
    Input("on-ground-container", "id"),
    prevent_initial_call=False
)
def update_table(_):
    try:
        # Get data with automatic caching
        table_name = "last_timestamp"
        df = query_cache(table_name)
        
        # Filter for on_ground planes
        if 'on_ground' in df.columns:
            df = df[df['on_ground'] == True]
        
        # Select and rename columns
        display_cols = []
        for col in ['callsign', 'icao24', 'origin_country', 'longitude', 'latitude', 'time_position', 'squawk']:
            if col in df.columns:
                display_cols.append(col)
                
        if len(display_cols) > 0:
            df = df[display_cols]
        
        # If we have position time, format it better
        if 'time_position' in df.columns:
            df['time_position'] = pd.to_datetime(df['time_position']).dt.strftime('%Y-%m-%d %H:%M:%S')
            
        # Create datatable
        if len(df) > 0:
            table = dash_table.DataTable(
                data=df.to_dict('records'),
                columns=[{'name': col.capitalize().replace('_', ' '), 'id': col} for col in df.columns],
                page_size=15,
                style_header={
                    'backgroundColor': 'rgb(230, 230, 230)',
                    'fontWeight': 'bold'
                },
                style_cell={
                    'textAlign': 'left',
                    'padding': '15px'
                },
                style_data_conditional=[
                    {
                        'if': {'row_index': 'odd'},
                        'backgroundColor': 'rgb(248, 248, 248)'
                    }
                ],
                filter_action="native",
                sort_action="native",
                sort_mode="multi"
            )
            
            return [
                html.Div(f"Showing {len(df)} aircraft currently on ground", className="mb-3"),
                table
            ]
        else:
            return html.Div("No aircraft currently on ground.", className="alert alert-info")
        
    except Exception as e:
        print(f"Error in on_ground update_table: {str(e)}")
        traceback.print_exc()
        return html.Div(f"Error loading data: {str(e)}", className="alert alert-danger") 