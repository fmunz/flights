import os
import pandas as pd
from databricks import sql
import json
from datetime import datetime
import dash
import numpy as np
import inspect
import yaml

# Load config from YAML file once at module load
def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

config = load_config()

def get_connection():
    try:
        return sql.connect(
            server_hostname=config["db_host"],
            http_path=config["db_http_path"],
            access_token=config["db_token"]
        )
    except KeyError as e:
        raise RuntimeError(f"Missing required config value: {e.args[0]}")
    except Exception as e:
        print(f"Error creating Databricks connection: {str(e)}")
        raise

def _query_table(table_name):
    """
    Query a table directly from the database.
    This is a helper function that should not generally be called directly.
    Instead, use query_cache which provides caching.
    """
    catalog = config["catalog"]
    schema = config["schema"]
    host = config["db_host"]
    token = config["db_token"]
    http_path = config["db_http_path"]

    print(f"[DEBUG] Using catalog: {catalog}, schema: {schema}")
    
    caller = get_caller_info()
    
    try:
        with sql.connect(
            server_hostname=host,
            http_path=http_path,
            access_token=token
        ) as connection:
            with connection.cursor() as cursor:
                query = f"SELECT * FROM {catalog}.{schema}.{table_name}"
                print(f"[Data Access from {caller}] Executing query: {query}")
                cursor.execute(query)
                result = cursor.fetchall()
                df = pd.DataFrame(result, columns=[col[0] for col in cursor.description])
                print(f"Query returned {len(df)} rows")
                return df
    except KeyError as e:
        raise RuntimeError(f"Missing required config value: {e.args[0]}")
    except Exception as e:
        print(f"Error in query_table from {caller}: {str(e)}")
        return None

def query_table(table_name):
    return _query_table(table_name)

def get_latest_flights(selected_country):   # selected_country is a string
    """
    Fetch the latest timestamped flight data from the configured catalog and schema.
    Returns a pandas DataFrame.
    """
    catalog = config["catalog"]
    schema = config["schema"]
    host = config["db_host"]
    token = config["db_token"]
    http_path = config["db_http_path"]

    where_clause = f"WHERE origin_country = '{selected_country}'" if selected_country else ""

    query = f"""
WITH latest_timestamp AS (
  SELECT MAX(timestamp) as max_ts
  FROM {catalog}.{schema}.opensky_raw
)
SELECT 
  to_utc_timestamp(timestamp, 'UTC') AS ts_ingest_time,
  CAST(cf.time_position AS TIMESTAMP) AS ts_time_position,
  CAST(cf.last_contact AS TIMESTAMP) AS ts_last_contact,
  date_format(to_utc_timestamp(timestamp, 'UTC'), "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'") AS ingest_time,
  -- date_format(timestamp, "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'") AS ingest_time,
  date_format(FROM_UNIXTIME(cf.time_position), "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'") AS time_position,
  date_format(FROM_UNIXTIME(cf.last_contact), "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'") AS last_contact,
  cf.* EXCEPT (time_position, last_contact, timestamp)
FROM {catalog}.{schema}.opensky_raw cf
JOIN latest_timestamp lt 
  ON cf.timestamp = lt.max_ts
{where_clause}
"""

    try:
        with sql.connect(
            server_hostname=host,
            http_path=http_path,
            access_token=token
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                result = cursor.fetchall()
                # Print first row of raw SQL result
                #print("Raw SQL result:", next(iter(result)))
                # Print column types from cursor
                #print("Cursor description:", [(col[0], col[1]) for col in cursor.description])

                
                df = pd.DataFrame(result, columns=[col[0] for col in cursor.description])
                #print("Pandas dtypes:", df.dtypes)
                #print("First row:", df.iloc[0])

                return df
    except KeyError as e:
        raise RuntimeError(f"Missing required config value: {e.args[0]}")
    except Exception as e:
        print(f"Error in get_latest_flight_data: {str(e)}")
        return pd.DataFrame()

def get_caller_info():
    try:
        caller_frame = inspect.currentframe().f_back.f_back
        caller_module = inspect.getmodule(caller_frame)
        caller_function = caller_frame.f_code.co_name
        if caller_module and hasattr(caller_module, '__file__'):
            caller_filename = os.path.splitext(os.path.basename(caller_module.__file__))[0]
            return f"{caller_filename}.{caller_function}"
        elif caller_module:
            return f"{caller_module.__name__}.{caller_function}"
        else:
            return caller_function
    except Exception:
        return "unknown"

def query_cache(table_name):
    cache_settings = {
        "countries": 60,        # Countries data can be cached for 1 minute        
        "last_timestamp": 3,    # Flight data needs to be fresh (10 seconds)
        "all_flights": 60       # 30 seconds cache for all flights
    }
    max_age_seconds = cache_settings.get(table_name, 0)
    if not hasattr(query_cache, '_cache'):
        query_cache._cache = {}
        query_cache._cache_hits = 0
    if (table_name in query_cache._cache and max_age_seconds > 0):
        cached_entry = query_cache._cache[table_name]
        cache_time = cached_entry.get('timestamp')
        cache_age = (datetime.now() - cache_time).total_seconds()
        if cache_age < max_age_seconds:
            query_cache._cache_hits += 1
            return cached_entry['data']
    caller = get_caller_info()
    print(f"[Data Access from {caller}] Querying database for {table_name} after {query_cache._cache_hits} cache hits")
    query_cache._cache_hits = 0  # Reset counter after db access
    df = _query_table(table_name)
    if df is not None and max_age_seconds > 0:
        query_cache._cache[table_name] = {
            'data': df,
            'timestamp': datetime.now()
        }
    return df

def get_all_flights():
    try:
        df = query_cache("all_flights")
        if df is not None and not df.empty:
            return df
        caller = get_caller_info()
        print(f"[Data Access from {caller}] No flight data available")    
        return df
    except Exception as e:
        caller = get_caller_info()
        print(f"[Data Access from {caller}] Error retrieving flight data: {str(e)}")
        return pd.DataFrame()  # Return empty DataFrame on error