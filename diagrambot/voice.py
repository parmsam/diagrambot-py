"""
Voice-enabled diagrambot Shiny application.
"""

import base64
import json
import zlib
from pathlib import Path
from typing import Any, Dict

import shinychat
from dotenv import load_dotenv
from faicons import icon_svg
from shiny import App, Inputs, Outputs, Session, reactive, render, req, ui
from shinyrealtime import realtime_server, realtime_ui


from .utils import ensure_openai_api_key, build_prompt

load_dotenv()

pricing_gpt4_realtime = {
    "input_text": 4 / 1e6,
    "input_audio": 32 / 1e6,
    "input_image": 5 / 1e6,
    "input_text_cached": 0.4 / 1e6,
    "input_audio_cached": 0.4 / 1e6,
    "input_image_cached": 0.5 / 1e6,
    "output_text": 16 / 1e6,
    "output_audio": 64 / 1e6,
}

pricing_gpt_4o_mini = {
    "input_text": 0.6 / 1e6,
    "input_audio": 10 / 1e6,
    "input_text_cached": 0.3 / 1e6,
    "input_audio_cached": 0.3 / 1e6,
    "output_text": 2.4 / 1e6,
    "output_audio": 20 / 1e6,
}


def hidden_audio_el(id: str, file_path: str, media_type: str = "audio/mp3"):
    """Create a hidden HTML audio element with embedded audio data."""
    file_path = Path(file_path)
    if not file_path.exists():
        return ui.HTML("")

    # Read binary data from file
    raw_data = file_path.read_bytes()

    # Encode to base64
    base64_data = base64.b64encode(raw_data).decode("utf-8")

    # Create data URI
    data_uri = f"data:{media_type};base64,{base64_data}"

    # Return HTML audio element
    return ui.HTML(
        f'<audio id="{id}" src="{data_uri}" style="display:none;" preload="auto"></audio>'
    )


def base64_to_base64url(base64_str: str) -> str:
    """Convert base64 to base64url encoding."""
    return base64_str.replace("+", "-").replace("/", "_").rstrip("=")


def create_kroki_encoding(code: str) -> str:
    """Create URL-safe encoding for Kroki (deflate + base64url)."""
    # Compress using zlib (equivalent to Python's gzip)
    compressed = zlib.compress(code.encode('utf-8'))
    base64_encoded = base64.b64encode(compressed).decode('utf-8')
    return base64_to_base64url(base64_encoded)


def generate_external_links_content(code: str, diagram_type: str) -> ui.TagList:
    """Generate external links for diagrams."""
    if diagram_type == "mermaid":
        # Create Mermaid Ink link using base64url encoding
        mermaid_ink_encoded = base64_to_base64url(
            base64.b64encode(code.encode('utf-8')).decode('utf-8')
        )
        mermaid_ink_url = f"https://mermaid.ink/img/{mermaid_ink_encoded}"

        # Create Mermaid Live Editor link using JSON format
        mermaid_json = json.dumps({
            "code": code,
            "mermaid": {"theme": "default"}
        })
        mermaid_live_encoded = base64_to_base64url(
            base64.b64encode(mermaid_json.encode('utf-8')).decode('utf-8')
        )
        mermaid_live_url = f"https://mermaid.live/edit#base64:{mermaid_live_encoded}"

        return ui.TagList(
            ui.div(
                {"class": "mb-3"},
                ui.h6("🖼️ Mermaid Ink (Image)"),
                ui.p(
                    {"class": "small text-muted"},
                    "Direct link to PNG image - great for embedding in documents"
                ),
                ui.HTML(f'''
                    <div class="input-group mb-2">
                        <input type="text" class="form-control font-monospace small" 
                               value="{mermaid_ink_url}" readonly onclick="this.select()">
                        <button class="btn btn-outline-secondary" type="button"
                                onclick="navigator.clipboard.writeText('{mermaid_ink_url}')">
                            <i class="fas fa-copy"></i> Copy
                        </button>
                        <button class="btn btn-primary" type="button"
                                onclick="window.open('{mermaid_ink_url}', '_blank')">
                            <i class="fas fa-external-link"></i> Open
                        </button>
                    </div>
                ''')
            ),
            ui.div(
                {"class": "mb-3"},
                ui.h6("✏️ Mermaid Live Editor"),
                ui.p(
                    {"class": "small text-muted"},
                    "Interactive editor for viewing and editing your diagram"
                ),
                ui.HTML(f'''
                    <div class="input-group mb-2">
                        <input type="text" class="form-control font-monospace small" 
                               value="{mermaid_live_url}" readonly onclick="this.select()">
                        <button class="btn btn-outline-secondary" type="button"
                                onclick="navigator.clipboard.writeText('{mermaid_live_url}')">
                            <i class="fas fa-copy"></i> Copy
                        </button>
                        <button class="btn btn-primary" type="button"
                                onclick="window.open('{mermaid_live_url}', '_blank')">
                            <i class="fas fa-external-link"></i> Open
                        </button>
                    </div>
                ''')
            )
        )
    elif diagram_type == "graphviz":
        # Create Kroki links using deflate+base64url encoding
        encoded_code = create_kroki_encoding(code)
        kroki_svg_url = f"https://kroki.io/graphviz/svg/{encoded_code}"
        kroki_png_url = f"https://kroki.io/graphviz/png/{encoded_code}"

        return ui.TagList(
            ui.div(
                {"class": "mb-3"},
                ui.h6("📊 Kroki (SVG)"),
                ui.p(
                    {"class": "small text-muted"},
                    "Scalable vector graphics - perfect for high-quality displays"
                ),
                ui.HTML(f'''
                    <div class="input-group mb-2">
                        <input type="text" class="form-control font-monospace small" 
                               value="{kroki_svg_url}" readonly onclick="this.select()">
                        <button class="btn btn-outline-secondary" type="button"
                                onclick="navigator.clipboard.writeText('{kroki_svg_url}')">
                            <i class="fas fa-copy"></i> Copy
                        </button>
                        <button class="btn btn-primary" type="button"
                                onclick="window.open('{kroki_svg_url}', '_blank')">
                            <i class="fas fa-external-link"></i> Open
                        </button>
                    </div>
                ''')
            ),
            ui.div(
                {"class": "mb-3"},
                ui.h6("🖼️ Kroki (PNG)"),
                ui.p(
                    {"class": "small text-muted"},
                    "Portable network graphics - ideal for embedding in documents"
                ),
                ui.HTML(f'''
                    <div class="input-group mb-2">
                        <input type="text" class="form-control font-monospace small" 
                               value="{kroki_png_url}" readonly onclick="this.select()">
                        <button class="btn btn-outline-secondary" type="button"
                                onclick="navigator.clipboard.writeText('{kroki_png_url}')">
                            <i class="fas fa-copy"></i> Copy
                        </button>
                        <button class="btn btn-primary" type="button"
                                onclick="window.open('{kroki_png_url}', '_blank')">
                            <i class="fas fa-external-link"></i> Open
                        </button>
                    </div>
                ''')
            )
        )
    else:
        return ui.div(
            {"class": "alert alert-info"},
            ui.HTML('<i class="fas fa-info-circle me-2"></i>'),
            "No external links available for this diagram type"
        )


def render_diagram_output(code: str, diagram_type: str) -> ui.HTML:
    """Render diagram output with error handling."""
    import random
    
    if diagram_type == "graphviz":
        diagram_id = f"graphviz-{random.randint(10000, 99999)}"
        escaped_code = code.replace("`", "\\`").replace("\\", "\\\\")
        return ui.HTML(f'''
            <div id="{diagram_id}" style="width: 100%; height: 100%; min-height: 400px;">
                <script>
                    setTimeout(function() {{ 
                        renderGraphvizDiagram('{diagram_id}', `{escaped_code}`); 
                    }}, 500);
                </script>
            </div>
        ''')
    else:  # mermaid
        diagram_id = f"mermaid-{random.randint(10000, 99999)}"
        escaped_code = code.replace("`", "\\`").replace("\\", "\\\\")
        return ui.HTML(f'''
            <div id="{diagram_id}" style="width: 100%; height: 100%; min-height: 400px;">
                <script>
                    setTimeout(function() {{ 
                        renderMermaidDiagram('{diagram_id}', `{escaped_code}`); 
                    }}, 500);
                </script>
            </div>
        ''')


def create_diagram_tool(last_code, last_diagram_type, debug=False):
    """Create diagram generation tool for realtime API."""
    async def generate_diagram(code: str, diagram_type: str):
        """Generate a diagram from code and diagram type."""
        if debug:
            print(f"Generating {diagram_type} diagram with code:\n{code}")
        
        # Set the reactive values
        last_code.set(code)
        last_diagram_type.set(diagram_type)
        
        return None  # Tool doesn't need to return anything
    
    return generate_diagram


def diagrambot_voice(
    prompt_file: str = None,
    voice: str = "cedar",
    speed: float = 1.1,
    debug: bool = False,
    launch_browser: bool = True,
    port: int = 0
) -> App:
    """
    Create a voice-enabled diagrambot Shiny application.
    
    Args:
        prompt_file: Path to the prompt file (defaults to bundled prompt)
        voice: Voice to use for audio responses
        speed: Speech speed
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
    app_ui = ui.page_sidebar(
        ui.sidebar(
            ui.help_text("Session cost:", ui.output_text("session_cost", inline=True)),
            shinychat.output_markdown_stream("response_text"),
        ),
        # Settings button in top right corner
        ui.div(
            ui.input_action_button(
                "settings_btn",
                "",
                icon=icon_svg("gear"),
                class_="btn-default",
                style="""position: fixed; top: 10px; right: 20px; z-index: 100001;
                        margin-left: auto; padding: 0.2rem 0.4rem; font-size: 1.1rem; 
                        height: 2rem; width: 2rem; min-width: 2rem; border: none; 
                        background: transparent; color: #495057; border-radius: 50%; 
                        display: flex; align-items: center; justify-content: center; 
                        box-shadow: none;""",
                title="Personal Instructions"
            )
        ),
        ui.card(
            ui.card_header("Diagram"),
            ui.card_body(ui.output_ui("diagram_output", fill=True), padding=0),
            height="66%",
            full_screen=True,
        ),
        ui.layout_columns(
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
                ui.card_body(ui.output_code("code_text", placeholder=False)),
                full_screen=True,
            ),
            height="34%",
        ),
        realtime_ui(
            "realtime1",
            style="z-index: 100000; margin-left: auto; margin-right: auto;",
            right=None,
        ),
        hidden_audio_el("shutter", str(Path(__file__).parent / "assets" / "shutter.mp3")),
        ui.tags.head(
            ui.include_js(Path(__file__).parent / "assets" / "www" / "diagram-renderers.js"),
            ui.include_js(Path(__file__).parent / "assets" / "www" / "personal-instructions.js"),
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
        title="diagrambot",
        fillable=True,
        style="--bslib-spacer: 1rem; padding-bottom: 0;",
    )
    
    # Server
    def server(input: Inputs, output: Outputs, session: Session):
        last_code = reactive.value()
        last_diagram_type = reactive.value("mermaid")
        running_cost = reactive.value(0)
        user_instructions = reactive.value("")

        # Pricing for GPT-4 Realtime API
        pricing_gpt4_realtime = {
            "input_text": 4 / 1e6,
            "input_audio": 32 / 1e6,
            "input_image": 5 / 1e6,
            "input_text_cached": 0.4 / 1e6,
            "input_audio_cached": 0.4 / 1e6,
            "input_image_cached": 0.5 / 1e6,
            "output_text": 16 / 1e6,
            "output_audio": 64 / 1e6,
        }

        # Handle instructions from localStorage
        instructions_ready = reactive.value(False)
        realtime_server_created = reactive.value(False)
        
        @reactive.effect
        @reactive.event(input.user_instructions_from_storage, ignore_none=False)
        def _handle_stored_instructions():
            """Load instructions from localStorage when available."""
            try:
                stored_value = input.user_instructions_from_storage()
                # Set the value even if it's empty
                user_instructions.set(stored_value if stored_value else "")
                if debug:
                    print(f"Loaded instructions from localStorage: '{stored_value}'")
            except Exception as e:
                if debug:
                    print(f"Error loading stored instructions: {e}")
            finally:
                # Mark as ready regardless
                instructions_ready.set(True)

        # Create diagram generation tool
        generate_diagram_tool = create_diagram_tool(
            last_code, last_diagram_type, debug=debug
        )

        response_text = shinychat.MarkdownStream("response_text")

        # Wait for instructions to load (with timeout) before creating realtime server
        @reactive.effect
        @reactive.event(instructions_ready)
        def _create_realtime_server_when_ready():
            """Create realtime server once instructions are loaded - ONLY RUNS ONCE."""
            # Ensure this only runs once
            if realtime_server_created():
                return
                
            print("=== Creating realtime server ===")
            print(f"instructions_ready: {instructions_ready()}")
            
            if not instructions_ready():
                print("Instructions not ready yet, returning")
                return
            
            # Mark that we're creating the server (prevent re-creation)
            realtime_server_created.set(True)
            
            # Build prompt with user instructions
            with reactive.isolate():
                user_instr = user_instructions()
            
            print(f"=== Building prompt with user instructions ===")
            print(f"User instructions: '{user_instr}'")
            
            if user_instr:
                complete_prompt = f"{prompt}\n\n## Additional User Context\n\n{user_instr}"
                print(f"Added user instructions to prompt")
            else:
                complete_prompt = prompt
                print(f"No user instructions, using base prompt only")
            
            if debug:
                print("Creating realtime server...")
                print(f"User instructions: '{user_instr}'")
                print(f"Complete prompt length: {len(complete_prompt)} characters")
            
            print(f"Complete prompt (first 200 chars): {complete_prompt[:200]}...")
            print(f"Complete prompt (last 200 chars): ...{complete_prompt[-200:]}")

            # Create realtime server with complete prompt including user instructions
            realtime_controls = realtime_server(
                "realtime1",
                voice=voice,
                instructions=complete_prompt,
                tools=[generate_diagram_tool],
                speed=speed,
            )

            greeting = "Welcome to diagrambot!\n\nYou're currently muted; click the mic button to unmute, click-and-hold the mic for push-to-talk, or hold the spacebar key for push-to-talk."

            @reactive.effect
            async def _stream_greeting():
                """Stream a greeting message on startup"""
                await response_text.stream([greeting])

            # Handle realtime events
            @realtime_controls.on("conversation.item.added")
            async def _show_coding_progress(event: dict[str, Any]):
                """Add notifications when function calls start"""
                if event["item"]["type"] == "function_call":
                    ui.notification_show(
                        "Generating diagram, please wait...",
                        id=event["item"]["id"],
                        close_button=False,
                    )

            @realtime_controls.on("conversation.item.done")
            async def _hide_coding_progress(event: dict[str, Any]):
                """Remove notifications when function calls complete"""
                if event["item"]["type"] == "function_call":
                    ui.notification_remove(id=event["item"]["id"])

            @realtime_controls.on("response.created")
            async def _clear_transcript(event: Dict[str, Any]):
                """Clear the transcript when a new response starts"""
                await response_text.stream([""], clear=True)

            @realtime_controls.on("response.output_audio_transcript.delta")
            async def _stream_text_to_transcript(event: Dict[str, Any]):
                """Stream text deltas to the transcript"""
                await response_text.stream([event["delta"]], clear=False)

            @realtime_controls.on("response.done")
            async def _track_session_cost(event):
                """Track session cost"""
                usage = event.get("response", {}).get("usage", {})
                if not usage:
                    return

                input_token_details = usage.get("input_token_details", {})
                output_token_details = usage.get("output_token_details", {})
                cached_tokens_details = input_token_details.get("cached_tokens_details", {})

                current_response = {
                    "input_text": input_token_details.get("text_tokens", 0),
                    "input_audio": input_token_details.get("audio_tokens", 0),
                    "input_image": input_token_details.get("image_tokens", 0),
                    "input_text_cached": cached_tokens_details.get("text_tokens", 0),
                    "input_audio_cached": cached_tokens_details.get("audio_tokens", 0),
                    "input_image_cached": cached_tokens_details.get("image_tokens", 0),
                    "output_text": output_token_details.get("text_tokens", 0),
                    "output_audio": output_token_details.get("audio_tokens", 0),
                }

                # Calculate cost
                cost = 0
                for k, v in current_response.items():
                    if k in pricing_gpt4_realtime:
                        cost += v * pricing_gpt4_realtime[k]

                with reactive.isolate():
                    running_cost.set(running_cost() + cost)

        # Show settings modal
        @reactive.effect
        @reactive.event(input.settings_btn)
        def _show_settings_modal():
            ui.modal_show(
                ui.modal(
                    ui.input_text_area(
                        "user_instructions_input",
                        "Add your personal context or instructions:",
                        value=user_instructions(),
                        placeholder="e.g., I work in healthcare and prefer medical terminology...",
                        rows=8,
                        width="100%"
                    ),
                    ui.help_text(
                        "These instructions will be added to the AI's system prompt. "
                        "You'll need to refresh the page to apply the changes."
                    ),
                    title="Personal Instructions",
                    footer=ui.TagList(
                        ui.modal_button("Cancel"),
                        ui.input_action_button(
                            "save_instructions",
                            "Save & Apply",
                            class_="btn-primary"
                        )
                    ),
                    size="m",
                    easy_close=True
                )
            )

        # Handle saving instructions
        @reactive.effect
        @reactive.event(input.save_instructions)
        async def _save_instructions():
            print("=== SAVE INSTRUCTIONS HANDLER CALLED ===")
            new_instructions = input.user_instructions_input()
            print(f"New instructions value: '{new_instructions}'")
            user_instructions.set(new_instructions)
            
            if debug:
                print(f"Saving instructions: '{new_instructions}'")
            
            # Send message to JavaScript to save to localStorage
            await session.send_custom_message(
                "save_instructions",
                {"instructions": new_instructions}
            )
            
            print("Custom message sent to JavaScript")
            if debug:
                print("Custom message sent to JavaScript")
            
            ui.modal_remove()
            
            # Show notification that refresh is needed
            ui.notification_show(
                ui.HTML(
                    "Personal instructions saved! "
                    "<strong>Please refresh the page</strong> to apply the changes. "
                    "(The instructions will be used on the next session.)"
                ),
                type="message",
                duration=None,  # Don't auto-dismiss
                close_button=True
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
                # Generate the external links content
                links_content = generate_external_links_content(code, diagram_type)
                
                # Show modal with the links
                ui.modal_show(
                    ui.modal(
                        ui.p("Share your diagram using these external services:"),
                        links_content,
                        title=ui.TagList(
                            ui.HTML('<i class="fas fa-external-link me-2"></i>'),
                            "External Links"
                        ),
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

        # Handle copy to clipboard button
        @reactive.Effect
        @reactive.event(input.copy_code)
        async def _copy_code():
            if not last_code():
                return
                
            code_to_copy = last_code()
            
            # Send the code to the browser for copying
            await session.send_custom_message(
                "copy_to_clipboard",
                {"text": code_to_copy}
            )
            
            # Show a temporary notification
            ui.notification_show(
                "Code copied to clipboard!",
                type="message",
                duration=2
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
        def session_cost():
            return f"${running_cost():.4f}"

    app = App(app_ui, server, debug=debug)
    
    if __name__ == "__main__":
        app.run(launch_browser=launch_browser, port=port)
    
    return app


def diagrambot(debug: bool = False):
    """
    Alias for diagrambot_voice for compatibility.
    """
    return diagrambot_voice(debug=debug)
