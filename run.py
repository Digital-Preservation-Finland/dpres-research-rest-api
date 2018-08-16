"""Simple script to run a development server"""

from research_rest_api import app


if __name__ == "__main__":
    app.create_app().run(debug=True, host="0.0.0.0", port=5001)
