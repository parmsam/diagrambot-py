"""
DiagramBot Voice App

A voice-enabled diagramming application using OpenAI's Realtime API.
Development version - sources directly from local diagrambot folder.
"""

from diagrambot.voice import diagrambot_voice
import shiny

# Create the app instance for development
app = diagrambot_voice(
    voice="cedar",
    speed=1.1,
    debug=True,  # Enable debug mode for development
    launch_browser=True,
    port=0
)

if __name__ == "__main__":
    # Run the app
    app.run()