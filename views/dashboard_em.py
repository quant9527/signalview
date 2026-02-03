import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from views.dashboard import render_dashboard

# Render dashboard with EM exchange preset
render_dashboard("em")
