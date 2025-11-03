"""
Chat-based diagrambot functionality.
"""

import json
import zlib
import base64
import os
from pathlib import Path
from typing import Any, Dict

from chatlas import ChatOpenAI
from shiny import App, Inputs, Outputs, Session, reactive, render, ui
from dotenv import load_dotenv

from .utils import ensure_openai_api_key, build_prompt

load_dotenv()

# Import helper functions from voice.py
from .voice import (
    hidden_audio_el,
    base64_to_base64url,
    create_kroki_encoding,
    generate_external_links_content,
    render_diagram_output,
)


def create_chat_diagram_tool(last_code, last_diagram_type, debug=False):
    """Create diagram generation tool for chat interface."""
    
    def generate_diagram(code: str, diagram_type: str):
        """Generate a diagram from code and diagram type.
        
        Args:
            code: The diagram code (Mermaid or Graphviz DOT syntax)
            diagram_type: The type of diagram ('mermaid' or 'graphviz')
        """
        if debug:
            print(f"Generating {diagram_type} diagram with code:\n{code}")
        
        # Set the reactive values
        last_code.set(code)
        last_diagram_type.set(diagram_type)
        
        return f"Generated {diagram_type} diagram successfully."
    
    return generate_diagram


def diagrambot_chat(
    prompt_file: str = None,
    debug: bool = False,
    launch_browser: bool = True,
    port: int = 0
) -> App:
    """
    Create a text-based chat diagrambot Shiny application.
    
    Args:
        prompt_file: Path to the prompt file (defaults to bundled prompt)
        debug: Enable debug mode
        launch_browser: Launch browser automatically
        port: Port to run on (0 for auto)
        
    Returns:
        Shiny App instance
    """
    
    # Ensure OpenAI API key is available
    ensure_openai_api_key()
    
    # Load prompt
    prompt = build_prompt(prompt_file)
    
    # UI
    app_ui = ui.page_fillable(
        ui.layout_sidebar(
            ui.sidebar(
                ui.help_text(
                    "Cost: ",
                    ui.output_text("session_cost_chat", inline=True),
                    " | Tokens: ",
                    ui.output_text("session_tokens_chat", inline=True)
                ),
                ui.card(
                    ui.card_header("Diagram"),
                    ui.card_body(ui.output_ui("diagram_output", fill=True), padding=0),
                    height="45vh",
                    full_screen=True,
                ),
                ui.card(
                    ui.card_header(
                        "Code",
                        ui.div(
                            ui.input_action_button(
                                "copy_code",
                                "Copy to Clipboard",
                                icon=ui.HTML('<i class="fas fa-copy"></i>'),
                                style="padding: 2px 8px; font-size: 12px; margin-top: -2px; margin-right: 5px;",
                                class_="btn-outline-secondary btn-sm"
                            ),
                            ui.input_action_button(
                                "external_links",
                                "External Links",
                                icon=ui.HTML('<i class="fas fa-external-link"></i>'),
                                style="padding: 2px 8px; font-size: 12px; margin-top: -2px;",
                                class_="btn-outline-primary btn-sm"
                            ),
                            style="float: right;"
                        )
                    ),
                    ui.card_body(ui.output_code("code_text")),
                    height="35vh",
                    full_screen=True,
                ),
                width=350,
            ),
            ui.chat_ui(id="chat"),
            fillable=True,
        ),
        hidden_audio_el("shutter", str(Path(__file__).parent / "assets" / "shutter.mp3")),
        ui.tags.head(
            ui.include_js(Path(__file__).parent / "assets" / "www" / "diagram-renderers.js"),
            ui.tags.script(
                """
                Shiny.addCustomMessageHandler("copy_to_clipboard", function(msg) {
                    console.log('Copy to clipboard handler called with:', msg);
                    const text = msg.text;
                    navigator.clipboard.writeText(text).then(function() {
                        console.log("Copied successfully:", text.substring(0, 50) + "...");
                    }).catch(function(err) {
                        console.warn("Copy failed:", err);
                        // Fallback method
                        try {
                            const textArea = document.createElement('textarea');
                            textArea.value = text;
                            textArea.style.position = 'fixed';
                            textArea.style.left = '-999999px';
                            textArea.style.top = '-999999px';
                            document.body.appendChild(textArea);
                            textArea.focus();
                            textArea.select();
                            document.execCommand('copy');
                            document.body.removeChild(textArea);
                            console.log("Copied using fallback method");
                        } catch (fallbackErr) {
                            console.error("Fallback copy also failed:", fallbackErr);
                        }
                    });
                });
                """
            )
        ),
        title="diagrambot chat",
        style="--bslib-spacer: 1rem;",
    )
    
    # Server
    def server(input: Inputs, output: Outputs, session: Session):
        last_code = reactive.value()
        last_diagram_type = reactive.value("mermaid")
        
        # Initialize ChatOpenAI client with system prompt
        chat_client = ChatOpenAI(
            model="gpt-4o",
            system_prompt=prompt
        )
        
        # Session tracking
        session_cost = reactive.value(0)
        session_tokens = reactive.value({"tokens": 0})
        
        # Create diagram generation tool function
        generate_diagram_func = create_chat_diagram_tool(
            last_code, last_diagram_type, debug=debug
        )
        
        # Register the tool with chat client
        chat_client.register_tool(generate_diagram_func)
        
        # Create the chat component using ui.Chat
        chat = ui.Chat(id="chat")
        
        # Define callback for user input
        @chat.on_user_submit
        async def handle_user_input(user_input: str):
            if debug:
                print(f"User input: {user_input}")
            
            try:
                # Get response from chat client (using stream for better UX)
                response = await chat_client.stream_async(user_input)
                
                # Add assistant response to chat using the correct method
                await chat.append_message_stream(response)
                
                # Update cost and token tracking using chatlas methods
                try:
                    cost = chat_client.get_cost()
                    session_cost.set(cost)
                    
                    tokens_list = chat_client.get_tokens()
                    total_tokens = sum(turn.get('tokens', 0) for turn in tokens_list) if tokens_list else 0
                    session_tokens.set({"tokens": total_tokens})
                    
                    if debug:
                        print(f"Updated cost: ${cost:.4f}, tokens: {total_tokens}")
                except Exception as tracking_error:
                    if debug:
                        print(f"Error updating usage tracking: {tracking_error}")
                
            except Exception as e:
                if debug:
                    print(f"Error in chat: {e}")
                await chat.append_message({
                    "content": f"Sorry, I encountered an error: {str(e)}", 
                    "role": "assistant"
                })
        
        # Periodic update for cost and token tracking (similar to R version)
        @reactive.effect
        def _update_usage_tracking():
            reactive.invalidate_later(5)  # Update every 5 seconds
            
            try:
                # Get cumulative cost and tokens
                cost = chat_client.get_cost()
                session_cost.set(cost)
                
                tokens_list = chat_client.get_tokens()
                total_tokens = sum(turn.get('tokens', 0) for turn in tokens_list) if tokens_list else 0
                session_tokens.set({"tokens": total_tokens})
                
                if debug:
                    print(f"Periodic update - Cost: ${cost:.4f}, Tokens: {total_tokens}")
                    
            except Exception as e:
                if debug:
                    print(f"Error in periodic usage tracking: {e}")
        
        # Handle copy to clipboard button
        @reactive.Effect
        @reactive.event(input.copy_code)
        async def _copy_code():
            print("=== COPY CODE BUTTON CLICKED (PYTHON SIDE) ===")
            if debug:
                print("Copy code button clicked")
                
            if not last_code():
                print("No code available to copy")
                if debug:
                    print("No code available to copy")
                ui.notification_show(
                    "No diagram code available to copy.",
                    type="warning",
                    duration=3
                )
                return
                
            code_to_copy = last_code()
            
            print(f"Code to copy length: {len(code_to_copy)} characters")
            print(f"Code preview: {code_to_copy[:100]}...")
            
            if debug:
                print(f"Copying code to clipboard: {code_to_copy[:50]}...")
            
            # Send the code to the browser for copying
            print("Sending custom message to browser")
            await session.send_custom_message(
                "copy_to_clipboard",
                {"text": code_to_copy}
            )
            print("Custom message sent")
            
            # Show a temporary notification
            ui.notification_show(
                "Code copied to clipboard!",
                type="message",
                duration=2
            )

        # Handle external links button
        @reactive.effect
        @reactive.event(input.external_links)
        def _show_external_links():
            if not last_code():
                ui.notification_show(
                    "No diagram code available to generate links.",
                    type="warning",
                    duration=3
                )
                return
                
            code = last_code()
            diagram_type = last_diagram_type()
            
            try:
                # Generate simple external links content
                if diagram_type == "mermaid":
                    # Create Mermaid Ink link
                    mermaid_ink_encoded = base64_to_base64url(
                        base64.b64encode(code.encode('utf-8')).decode('utf-8')
                    )
                    mermaid_ink_url = f"https://mermaid.ink/img/{mermaid_ink_encoded}"
                    
                    # Create Mermaid Live Editor link
                    mermaid_json = json.dumps({
                        "code": code,
                        "mermaid": {"theme": "default"}
                    })
                    mermaid_live_encoded = base64_to_base64url(
                        base64.b64encode(mermaid_json.encode('utf-8')).decode('utf-8')
                    )
                    mermaid_live_url = f"https://mermaid.live/edit#base64:{mermaid_live_encoded}"
                    
                    links_html = f"""
                    <div class="mb-3">
                        <h6>🖼️ Mermaid Ink (Image)</h6>
                        <p class="small text-muted">Direct link to PNG image</p>
                        <div class="input-group mb-2">
                            <input type="text" class="form-control" value="{mermaid_ink_url}" readonly onclick="this.select()">
                            <button class="btn btn-outline-secondary" onclick="window.open('{mermaid_ink_url}', '_blank')">Open</button>
                        </div>
                    </div>
                    <div class="mb-3">
                        <h6>✏️ Mermaid Live Editor</h6>
                        <p class="small text-muted">Interactive editor</p>
                        <div class="input-group mb-2">
                            <input type="text" class="form-control" value="{mermaid_live_url}" readonly onclick="this.select()">
                            <button class="btn btn-outline-secondary" onclick="window.open('{mermaid_live_url}', '_blank')">Open</button>
                        </div>
                    </div>
                    """
                    
                elif diagram_type == "graphviz":
                    # Create Kroki links
                    encoded_code = create_kroki_encoding(code)
                    kroki_svg_url = f"https://kroki.io/graphviz/svg/{encoded_code}"
                    kroki_png_url = f"https://kroki.io/graphviz/png/{encoded_code}"
                    
                    links_html = f"""
                    <div class="mb-3">
                        <h6>📊 Kroki (SVG)</h6>
                        <p class="small text-muted">Scalable vector graphics</p>
                        <div class="input-group mb-2">
                            <input type="text" class="form-control" value="{kroki_svg_url}" readonly onclick="this.select()">
                            <button class="btn btn-outline-secondary" onclick="window.open('{kroki_svg_url}', '_blank')">Open</button>
                        </div>
                    </div>
                    <div class="mb-3">
                        <h6>🖼️ Kroki (PNG)</h6>
                        <p class="small text-muted">Portable network graphics</p>
                        <div class="input-group mb-2">
                            <input type="text" class="form-control" value="{kroki_png_url}" readonly onclick="this.select()">
                            <button class="btn btn-outline-secondary" onclick="window.open('{kroki_png_url}', '_blank')">Open</button>
                        </div>
                    </div>
                    """
                else:
                    links_html = "<p>No external links available for this diagram type.</p>"
                
                # Show modal with the links
                ui.modal_show(
                    ui.modal(
                        ui.p("Share your diagram using these external services:"),
                        ui.HTML(links_html),
                        title="🔗 External Links",
                        footer=ui.modal_button("Close"),
                        size="l",
                        easy_close=True
                    )
                )
                
            except Exception as e:
                if debug:
                    print(f"Error generating external links: {e}")
                ui.notification_show(
                    f"Error generating external links: {str(e)}",
                    type="error",
                    duration=5
                )

        # Outputs
        @render.ui
        def diagram_output():
            if not last_code():
                return ui.div()
            
            code = last_code()
            diagram_type = last_diagram_type()
            return render_diagram_output(code, diagram_type)

        @reactive.effect(priority=-10)
        async def _play_shutter():
            if last_code():
                await session.send_custom_message("play_audio", {"selector": "#shutter"})

        @render.code
        def code_text():
            if last_code():
                return last_code()
            return ""

        @render.text
        def session_cost_chat():
            cost = session_cost()
            return f"${cost:.4f}"

        @render.text
        def session_tokens_chat():
            tokens_data = session_tokens()
            total_tokens = tokens_data.get("tokens", 0)
            return f"{total_tokens}"

    app = App(app_ui, server, debug=debug)
    
    if __name__ == "__main__":
        app.run(launch_browser=launch_browser, port=port)
    
    return app