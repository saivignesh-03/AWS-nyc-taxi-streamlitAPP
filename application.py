import os
import subprocess

# Start the streamlit app
subprocess.run(["streamlit", "run", "app.py", "--server.port=8080", "--server.enableCORS=false"])