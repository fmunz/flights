import os
import shutil
#from databricks.connect import DatabricksSession  # Not used in this script
from databricks.sdk import WorkspaceClient

def create_deployment_package():
    # Create a temporary directory for deployment
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    os.makedirs('dist')
    
    # Copy necessary files
    files_to_copy = [
        'app.py',
        'config.yaml',
        'requirements.txt',
        'README.md'
    ]
    
    for file in files_to_copy:
        shutil.copy2(file, f'dist/{file}')
    
    # Copy pages directory
    shutil.copytree('pages', 'dist/pages')
    
    # Copy utils directory
    shutil.copytree('utils', 'dist/utils')

def deploy_to_databricks():
    # Use environment variables for host and token
    host = os.getenv('DB_HOST')
    token = os.getenv('DB_TOKEN')
    if not all([host, token]):
        raise ValueError("Missing required Databricks connection parameters. Please set them in flights.env or as environment variables.")
    
    # Initialize Databricks workspace client
    workspace = WorkspaceClient(
        host=host,
        token=token
    )
    
    # Create deployment package
    create_deployment_package()
    
    # Create or update the app
    app_name = "flight-dashboard"
    
    # Upload the deployment package
    workspace.workspace.upload(
        f"/Workspace/Repos/{app_name}/dist",
        "dist",
        overwrite=True
    )
    
    # Create or update the app configuration
    app_config = {
        "name": app_name,
        "description": "Flight Dashboard using OpenSky API data",
        "entry_point": "app.py",
        "requirements": "requirements.txt",
        "timeout_seconds": 300,
        "max_retries": 3
    }
    
    try:
        workspace.apps.create(**app_config)
        print(f"App {app_name} created successfully!")
    except Exception as e:
        print(f"Error creating app: {str(e)}")
        # Try to update if creation fails
        try:
            workspace.apps.update(**app_config)
            print(f"App {app_name} updated successfully!")
        except Exception as e:
            print(f"Error updating app: {str(e)}")

if __name__ == "__main__":
    deploy_to_databricks() 