import dash
from dash import html, dcc, Output, Input, State, ALL, callback
import dash_bootstrap_components as dbc
from bokeh.resources import CDN
import importlib
import os
import sys
from utils.database import query_cache
from datetime import datetime


# Initialize the Dash app
app = dash.Dash(__name__, 
                external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
                external_scripts=CDN.js_files if CDN.js_files else [],
                use_pages=True,
                suppress_callback_exceptions=True,
                prevent_initial_callbacks='initial_duplicate',
                title="Lakeflow Declarative Pipelines - Flight Tracking")

# Dictionary mapping paths to display names
MENU_NAMES = {
    '/': 'Home',
    '/map': 'Static Map',
    '/streaming': 'Live Map',
    '/on_ground': 'Landed Table',
    '/heatmap': 'Old Heatmap',
    '/heatmapd': 'Heatmaps',
    '/debug': 'Debug',
    '/statistics': 'Real-time Flight Analytics Dashboard',
    '/stats': 'Statistics',
    '/stats2': 'Statistics2'
}

# Update the sidebar navigation with new buttons and renamed buttons
sidebar = html.Div(
    [
        html.H2("Lakeflow Declarative Pipelines - Flight Tracking", className="display-6"),
        html.Hr(),
        html.Div([
            dbc.Button(
                [html.I(className="fas fa-home me-2"), "Home"],
                href="/",
                color="primary",
                className="w-100 mb-2 text-start",
                id="home-btn"
            ),
            dbc.Button(
                [html.I(className="fas fa-chart-bar me-2"), "Statistics"],
                href="/statistics",
                color="primary",
                className="w-100 mb-2 text-start",
                id="statistics-btn"
            ),
            # Commented out Static Map button but kept the implementation
            # dbc.Button(
            #     [html.I(className="fas fa-map-marked-alt me-2"), "Static Map"],
            #     href="/flight-map",
            #     color="info",
            #     className="w-100 mb-2 text-start",
            #     id="map-btn"
            # ),
            dbc.Button(
                [html.I(className="fas fa-satellite me-2"), "Live Map"],
                href="/streaming",
                color="success",
                className="w-100 mb-2 text-start",
                id="streaming-btn"
            ),
            dbc.Button(
                [html.I(className="fas fa-plane-arrival me-2"), "Landed Table"],
                href="/on_ground",
                color="warning",
                className="w-100 mb-2 text-start",
                id="on-ground-btn"
            ),
            # Commented out Heatmaps button but kept the implementation
            # dbc.Button(
            #     [html.I(className="fas fa-fire-alt me-2"), "Heatmaps"],
            #     href="/heatmapd",
            #     color="danger",
            #     className="w-100 mb-2 text-start",
            #     id="heatmapd-btn"
            # ),
        ], className="d-grid gap-2"),
    ],
    className="sidebar",
)

# Top box for menu name
menu_name_box = html.Div(
    id="menu-name-box",
    children="",
    className="shadow-lg border-0 mb-4",
    style={
        "backgroundColor": "#fff",
        "padding": "1.5rem 2rem",
        "borderRadius": "1rem",
        "fontSize": "2.5rem",
        "fontWeight": "bold",
        "textAlign": "center",
        "letterSpacing": "0.02em",
        "minHeight": "4.5rem"
    }
)

# Define the app layout with sidebar, top box, and main content
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    sidebar,
    html.Div([
        menu_name_box,
        dash.page_container
    ], style={
        "marginLeft": "280px",
        "padding": "2rem 2rem 2rem 2rem",
        "minHeight": "100vh",
        "backgroundColor": "#f5f6fa"
    })
])

# Callback to update the menu name box based on the current page
@app.callback(
    Output("menu-name-box", "children"),
    Input("url", "pathname")
)
def update_menu_name(pathname):
    return MENU_NAMES.get(pathname, "")

# Update clientside callback to handle menu button highlighting
app.clientside_callback(
    """
    function(pathname) {
        // Reset all buttons
        const buttons = [
            "home-btn", "statistics-btn", "map-btn", "streaming-btn", "on-ground-btn", 
            "heatmapd-btn"
        ];
        buttons.forEach(id => {
            const button = document.getElementById(id);
            if (button) button.classList.remove("active");
        });
        
        // Map pathname to button ID
        const pathToId = {
            "/": "home-btn",
            "/statistics": "statistics-btn",
            "/flight-map": "map-btn",
            "/map": "map-btn",  // Support both paths
            "/streaming": "streaming-btn",
            "/on_ground": "on-ground-btn",
            "/heatmapd": "heatmapd-btn"
        };
        
        // Add active class to current button
        const currentId = pathToId[pathname];
        if (currentId) {
            const currentButton = document.getElementById(currentId);
            if (currentButton) currentButton.classList.add("active");
        }
        
        return window.dash_clientside.no_update;
    }
    """,
    Output("url", "search"),  # Dummy output that won't actually update
    Input("url", "pathname")
)

if __name__ == '__main__':
    app.run_server(debug=True) 