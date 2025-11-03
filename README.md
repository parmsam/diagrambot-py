# DiagramBot

diagrambot is an interactive Shiny app for creating Mermaid and Graphviz diagrams using AI. It helps you generate flowcharts, sequence diagrams, network graphs, organizational charts, and more through both voice commands (using GPT-4o Realtime) and text chat interfaces. diagrambot supports both Mermaid syntax for a wide variety of structured diagrams and Graphviz/DOT syntax for complex network and hierarchical visualizations. diagrambot is a Python rewrite of the [original diagrambot](https://github.com/parmsam/diagrambot) R package.

## Prerequisites

In order to use diagrambot, you will need an OpenAI API key. You can obtain one from the OpenAI dashboard. You'll also need to put at least a few dollars on your account to use the API.

Once you have an API key, you will need to set it as an environment variable named OPENAI_API_KEY. You can do this by adding the following line to an `.env` file in your project directory:

```
OPENAI_API_KEY=your_api_key_here
```

## Installation

You can install it directly from Github using:

```
pip install git+https://github.com/parmsam/diagrambot-py.git
```
## Example

See `app.py` for a complete working example that uses the library.