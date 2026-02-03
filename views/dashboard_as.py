import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from views.dashboard import render_dashboard

# Render dashboard with AS exchange preset
render_dashboard("as")
