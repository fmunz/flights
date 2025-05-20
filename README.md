# Flight Dashboard

A Dash application for visualizing flight data from OpenSky API, designed to be deployed as a Databricks app in the lake house.

## Project Structure

```
.
├── app.py              # Main application file
├── flights.env         # Flat configuration file for database settings
├── requirements.txt    # Python dependencies
└── pages/             # Page modules
    ├── statistics.py   # Statistics page
    ├── on_ground.py   # On Ground aircraft table
    └── flight_map.py  # Flight map visualization
```

## Setup

1. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure the application:
Create a `config.yaml` file in the project root with the following content:

```
catalog: demo_frank
schema: flights
db_host: e2-dogfood.staging.cloud.databricks.com
db_token: XXX
db_http_path: /sql/1.0/warehouses/7ea9411469196839
ui_refresh_interval: 10
```

- `catalog`: The Databricks catalog name
- `schema`: The Databricks schema name
- `db_host`: The Databricks SQL warehouse host
- `db_token`: The Databricks access token (replace XXX with your real token)
- `db_http_path`: The Databricks HTTP path
- `ui_refresh_interval`: Data refresh interval in seconds

## Running the Application

Run the application locally:
```bash
python app.py
```

The application will be available at `http://localhost:8050`

## Features

- Statistics page with flight statistics
- On Ground page showing aircraft currently on the ground
- Flight Map page displaying aircraft locations on a map

## Database Configuration

The application reads from the following tables in the configured catalog and schema:
- `on_ground`: Table containing aircraft on ground information
- `last_timestamp`: Table containing the latest aircraft positions 