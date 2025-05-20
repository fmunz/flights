import dash
from dash import html, dcc, register_page
import dash_bootstrap_components as dbc

# Register the page with the /map path
register_page(__name__, path="/map")

# Layout that redirects to /flight-map
layout = html.Div([
    # Client-side redirect using JavaScript
    html.Script('''
        window.location.href = "/flight-map";
    '''),
    # Fallback for no JavaScript
    dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H3("Redirecting to Flight Map...", className="text-center my-4"),
                html.P("If you are not redirected automatically, please click the link below:", className="text-center"),
                html.Div([
                    dbc.Button("Go to Flight Map", href="/flight-map", color="primary", size="lg")
                ], className="text-center")
            ])
        ])
    ])
]) 