"""
DiagramBot Chat App

A text-based diagramming application using OpenAI's Chat API.
Development version - sources directly from local diagrambot folder.
"""

from diagrambot.chat import diagrambot_chat
import shiny
# Create the app instance for development
app = diagrambot_chat(
    debug=True,  # Enable debug mode for development
    launch_browser=True,
    port=0
)

if __name__ == "__main__":
    # Run the app
    app.run()