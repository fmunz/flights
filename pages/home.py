import dash_bootstrap_components as dbc
from dash import html, register_page

register_page(__name__, path="/")

def layout():
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Img(
                            src="/static/plane.png",
                            style={
                                "maxWidth": "100%",
                                "maxHeight": "700px",
                                "objectFit": "contain"
                            },
                            className="mx-auto d-block"
                        )
                    ], className="d-flex justify-content-center align-items-center")
                ], className="shadow-lg border-0", style={"backgroundColor": "#fff", "borderRadius": "1rem"})
            ], width=10, lg=8, xl=6, className="mx-auto")
        ], className="justify-content-center align-items-center", style={"height": "85vh"})
    ], fluid=True) 