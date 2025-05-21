from datetime import datetime
import tzlocal

# Get system timezone
system_tz = tzlocal.get_localzone()
print(f"System timezone: {system_tz}")

# Check if it matches what Pandas is using
import pandas as pd
print(f"Pandas timezone: {pd.Timestamp.now().tz}")