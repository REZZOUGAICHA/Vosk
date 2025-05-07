from rapidfuzz import fuzz
from metaphone import doublemetaphone
import numpy as np
import asyncio
import websockets
import threading
import queue
import json
import os
import sys
import signal
import time

# Create a global queue for audio data
audio_queue = queue.Queue()
# Flag to track if we have an active WebSocket connection
websocket_active = False

async def handle_websocket(websocket):
    global websocket_active, active_websocket
    print("[WebSocket] Client connected")
    websocket_active = True  # Set the flag when client connects
    active_websocket = websocket  # Store the active connection
    
    try:
        async for message in websocket:
            # Silently queue audio data (no debug spam)
            audio_queue.put(message)
    except websockets.exceptions.ConnectionClosed:
        print("[WebSocket] Client disconnected")
    except Exception as e:
        print(f"[WebSocket Error] {e}")
    finally:
        websocket_active = False  # Reset the flag when client disconnects
        active_websocket = None  # Clear the active connection

# Add the global variable at the top of your file with other globals
audio_queue = queue.Queue()
websocket_active = False
active_websocket = None  # Store the active WebSocket connection

# ------------------------------------------------------------------------------------
def start_websocket_server():
    print("[Server] Initializing WebSocket server...")
    
    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def server_main():
        async with websockets.serve(handle_websocket, "0.0.0.0", 8765):
            print("[Server] WebSocket server is running on ws://0.0.0.0:8765")
            await asyncio.Future()  # run forever

    try:
        loop.run_until_complete(server_main())
    except Exception as e:
        print(f"[Server Error] WebSocket server encountered an error: {e}")
    finally:
        print("[Server] Closing event loop")
        loop.close()

# Start WebSocket server in a separate thread
websocket_thread = threading.Thread(
    target=start_websocket_server, 
    daemon=True
)
websocket_thread.start()
print("WebSocket server thread started")
# ------------------------------------------------------------------------------------
from scipy import signal

# Define speech detection functions
try:
    import webrtcvad
    print("VAD module imported successfully")
    
    def is_speech(data, sample_rate=16000, frame_duration=30):
        vad = webrtcvad.Vad(3)  # Aggressiveness level 3 (highest)
        frame_size = int(sample_rate * frame_duration / 1000)
        if len(data) >= frame_size:
            # Check if the frame is speech
            return vad.is_speech(data[:frame_size], sample_rate)
        return False
except ImportError:
    print("webrtcvad not installed, skipping VAD")
    
    def is_speech(data, sample_rate=16000, frame_duration=30):
        return True  # Always process audio if VAD is not available

# ------------------------------------------------------------------------------------
def is_similar(spoken_text, expected_command, threshold=80):
    # Direct match
    direct_score = fuzz.ratio(spoken_text, expected_command)
    
    # Partial match (for when command is embedded in longer text)
    partial_score = fuzz.partial_ratio(spoken_text, expected_command)
    
    # Token set ratio (handles word reordering)
    token_score = fuzz.token_set_ratio(spoken_text, expected_command)
    
    # Get best score
    best_score = max(direct_score, partial_score, token_score)
    return best_score >= threshold

def phonetic_match(word1, word2):
    return doublemetaphone(word1)[0] == doublemetaphone(word2)[0]

def preprocess_audio(data, sample_rate=16000):
    try:
        # Convert bytes to numpy array
        audio_data = np.frombuffer(data, dtype=np.int16)
        
        # Apply noise reduction (simple high-pass filter to remove low-frequency noise)
        b, a = signal.butter(5, 300/(sample_rate/2), 'highpass')
        filtered_data = signal.lfilter(b, a, audio_data)
        
        # Apply normalization
        if np.abs(filtered_data).max() > 0:
            normalized_data = filtered_data / np.abs(filtered_data).max() * 32767
        else:
            normalized_data = filtered_data
            
        # Convert back to bytes
        return normalized_data.astype(np.int16).tobytes()
    except Exception as e:
        print(f"Error in audio preprocessing: {e}")
        # If preprocessing fails, return original data
        return data

# Define command mapping
COMMANDS = {
    "stop": ["stop"],
    "start": ["start", "démarrer", "activez application"],
    "help": ["help", "aide"],
    "navigate": ["navigate to", "aller à"],
    "stop detection": ["stop detection", "arrêter détection"]
}

def detect_command(text):
    for cmd, variations in COMMANDS.items():
        if any(is_similar(text, phrase) for phrase in variations):
            return cmd
    return None
async def send_websocket_message(message):
    global active_websocket
    if active_websocket:
        await active_websocket.send(message)
        print(f"Message sent through WebSocket: {message}")
    else:
        print("No active WebSocket connection to send message")

def execute_command(text):
    # Convert to lowercase for easier matching
    text = text.lower()
    
    # General commands that work in any language
    detected_command = detect_command(text)
    
    # Handle special commands by sending them to the WebSocket client
    if "faire appel" in text or "call assistant" in text:
        print("\n Command: Contacting registered assistant")
    
        # Add this block - it modifies the recognition text that's printed
        # We know this is already being sent to the client
        recognizer.Result = lambda: json.dumps({"text": "faire appel TRIGGER_CALL"})
        
        # Send command to WebSocket client if connection is active
        if websocket_active:
            try:
                # Create a specific message that the client can easily identify
                command_message = "COMMAND:CALL_ASSISTANT"
                
                # Create a new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Run the coroutine
                loop.run_until_complete(send_websocket_message(command_message))
                
                # Close the loop when done
                loop.close()
                
                print(f"Command sent to client: {command_message}")
            except Exception as e:
                print(f"Error sending command to client: {e}")
    
    # Rest of your execute_command function remains the same...
    
    if detected_command == "stop":
        print("\n Command: SYSTEM_STOP")
        os._exit(0)
    
    if selected_lang == "en":
        # Basic System Commands
        if "start" in text or "activate application" in text:
            print("\n Command: INIT_SYSTEM - Starting the application")
        elif "main menu" in text:
            print("\n Command: Accessing main menu")
        elif "help" in text:
            print("\n Command: Displaying available commands")
        elif "reset" in text:
            print("\n Command: RESET_SYSTEM - Resetting system")
        elif "check status" in text:
            print("\n Command: CHECK_STATUS - Checking system status")
            
        # Navigation Commands
        elif "navigate to" in text:
            destination = text.split("navigate to")[1].strip()
            print(f"\n Command: START_NAVIGATION to {destination}")
        elif "start navigation" in text:
            print("\n Command: START_GUIDANCE - Starting navigation guidance")
        elif "stop navigation" in text:
            print("\n Command: STOP_NAVIGATION - Stopping navigation")
        elif "my position" in text:
            print("\n Command: UPDATE_POSITION - Getting current position")
        elif "recalculate route" in text:
            print("\n Command: RE_ROUTE - Recalculating route")
        elif "nearby obstacles" in text:
            print("\n Command: GET_OBJECT_LIST - Checking nearby obstacles")
        elif "turn left" in text:
            print("\n Command: NAV_INSTRUCTION left")
        elif "turn right" in text:
            print("\n Command: NAV_INSTRUCTION right")
        elif "go forward" in text or "continue" in text:
            print("\n Command: NAV_INSTRUCTION forward")
        elif "remaining distance" in text:
            print("\n Command: Getting remaining distance")
        elif "remaining time" in text:
            print("\n Command: Getting estimated remaining time")
            
        # POI Commands
        elif "search for" in text:
            poi_type = text.split("search for")[1].strip()
            print(f"\n Command: SEARCH_POI {poi_type}")
        elif "nearby points" in text or "nearby poi" in text:
            print("\n Command: Getting nearby points of interest")
        elif "information on" in text or "info on" in text:
            # Extract POI name after "information on" or "info on"
            poi_name = text.split("information on" if "information on" in text else "info on")[1].strip()
            print(f"\n Command: GET_POI_INFO {poi_name}")
        elif "set" in text and "as destination" in text:
            # Extract destination between "set" and "as destination"
            parts = text.split("as destination")[0].split("set")[1].strip()
            print(f"\n Command: SET_POI_AS_DEST {parts}")
            
        # Object Detection Commands
        elif "identify objects" in text:
            print("\n Command: START_OBJECT_DETECT - Starting object detection")
        elif "stop detection" in text:
            print("\n Command: STOP_OBJECT_DETECT - Stopping object detection")
        elif "detect obstacle" in text:
            print("\n Command: DETECT_OBSTACLE - Scanning for obstacles")
            
        # Battery and System Status
        elif "battery" in text:
            print("\n Command: POWER_STATUS - Checking battery status")
            
        # Communication Commands
        elif "share my location" in text:
            print("\n Command: Sharing current location")
        elif "find assistant" in text or "find helper" in text:
            print("\n Command: Searching for nearby assistance")
        elif "call assistant" in text:
            print("\n Command: Contacting registered assistant")
            
        elif "emergency" in text or "emergency" in text:
            print("\n Command: Initiating emergency call")
            
        # User Preferences
        elif "my preferences" in text:
            print("\n Command: SET_USER_PREFS - Accessing user preferences")
        elif "change language" in text:
            print("\n Command: Changing guidance language")

        elif "hello" in text:
            print("\n Hello, How can I help you?")
        else:
            print(f"\n Command not recognized: '{text}'")
    
    elif selected_lang == "fr":
        # Basic System Commands
        if "démarrer" in text or "activer l'application" in text:
            print("\n Command: INIT_SYSTEM - Démarrage de l'application")
        elif "menu principal" in text:
            print("\n Command: Accès au menu principal")
        elif "aide" in text:
            print("\n Command: Affichage des commandes disponibles")
        elif "réinitialiser" in text:
            print("\n Command: RESET_SYSTEM - Réinitialisation du système")
        elif "configurez système" in text:
            print("\n Command: INIT_SYSTEM - Configuration du système")
            
        # Navigation Commands
        elif "naviguez vers" in text:
            destination = text.split("naviguer vers")[1].strip()
            print(f"\n Command: START_NAVIGATION vers {destination}")
        elif "commencez navigation" in text:
            print("\n Command: START_GUIDANCE - Démarrage du guidage")
        elif "arrêtez navigation" in text:
            print("\n Command: STOP_NAVIGATION - Arrêt de la navigation")
        elif "ma position" in text:
            print("\n Command: UPDATE_POSITION - Position actuelle")
        elif "recalculer itinéraire" in text:
            print("\n Command: RE_ROUTE - Recalcul de l'itinéraire")
        elif "obstacle à proximité" in text:
            print("\n Command: GET_OBJECT_LIST - Vérification des obstacles proches")
        elif "tourne à gauche" in text:
            print("\n Command: NAV_INSTRUCTION left")
        elif "tourne à droite" in text:
            print("\n Command: NAV_INSTRUCTION right")
        elif "avancez" in text or "continuer" in text:
            print("\n Command: NAV_INSTRUCTION forward")
        elif "distance restante" in text:
            print("\n Command: Obtention de la distance restante")
        elif "temps restant" in text:
            print("\n Command: Obtention du temps estimé restant")
            
        # POI Commands
        elif "chercher" in text:
            poi_type = text.split("chercher")[1].strip()
            print(f"\n Command: SEARCH_POI {poi_type}")
        elif "pois à proximité" in text: 
            print("\n Command: Obtention des points d'intérêt proches")
        elif "information sur" in text:
            poi_name = text.split("information sur")[1].strip()
            print(f"\n Command: GET_POI_INFO {poi_name}")
        elif "définir" in text and "comme destination" in text:
            parts = text.split("comme destination")[0].split("définir")[1].strip()
            print(f"\n Command: SET_POI_AS_DEST {parts}")
            
        # Object Detection Commands
        elif "identifier objets" in text:
            print("\n Command: START_OBJECT_DETECT - Démarrage de la détection d'objets")
        elif "arrêtez détection" in text:
            print("\n Command: STOP_OBJECT_DETECT - Arrêt de la détection d'objets")
        elif "détecter obstacle" in text:
            print("\n Command: DETECT_OBSTACLE - Scan des obstacles")
            
        # Battery and System Status
        elif "la batterie" in text:
            print("\n Command: POWER_STATUS - Vérification de la batterie")
            
        # Communication Commands
        elif "partager ma localisation" in text:
            print("\n Command: Partage de la position actuelle")
        elif "trouver un aidant" in text:
            print("\n Command: Recherche d'assistance à proximité")
        elif "faire appel" in text:
            print("\n Command: Contact de l'aidant enregistré")
        elif "s o s" in text or "urgence" in text:
            print("\n Command: Initiating emergency call")
            
        # User Preferences
        elif "mes préférences" in text:
            print("\n Command: SET_USER_PREFS - Accès aux préférences utilisateur")
        elif "changer langue" in text:
            print("\n Command: Changement de la langue de guidage")
        elif "changer voix" in text:
            print("\n Command: Modification du genre de la voix")
        elif "ajustez vibrations" in text:
            print("\n Command: Accès aux réglages de vibration")
            
        elif "bonjour" in text:
            print("\n Bonjour, comment puis-je vous aider ?")
        elif "porte" in text:
            print("\n Command: Opening the door")
        else:
            print(f"\n Command non reconnue: '{text}'")

# Main try block that encapsulates the entire script
try:
    print("Starting script...")
    
    try:
        from vosk import Model, KaldiRecognizer
        print("Vosk imported successfully")
    except ImportError as e:
        print(f"Error importing Vosk: {e}")
        print("Try installing it with: pip install vosk")
        exit(1)
        
    try:
        import pyaudio
        print("PyAudio imported successfully")
    except ImportError as e:
        print(f"Error importing PyAudio: {e}")
        print("Try installing it with: pip install pyaudio")
        exit(1)
    
    print("All dependencies loaded successfully")
    
    # Check if model folders exist
    model_path_fr = "model_fr"
    model_path_en = "model_us"
    
    available_models = []
    
    if os.path.exists(model_path_en):
        available_models.append(("en", model_path_en))
    else:
        print(f"Warning: English model folder '{model_path_en}' not found in {os.getcwd()}")
    
    if os.path.exists(model_path_fr):
        available_models.append(("fr", model_path_fr))
    else:
        print(f"Warning: French model folder '{model_path_fr}' not found in {os.getcwd()}")

    if not available_models:
        print("Error: No language models found. Please download models from https://alphacephei.com/vosk/models")
        exit(1)
    
    # Language selection
    print("\n=== Language Selection ===")
    for idx, (lang, path) in enumerate(available_models):
        print(f"{idx+1}. {lang.upper()} ({path})")
    
    selected_idx = None
    while selected_idx is None:
        try:
            user_input = input("\nSelect language (enter number): ")
            selected_idx = int(user_input) - 1
            if selected_idx < 0 or selected_idx >= len(available_models):
                print(f"Please enter a number between 1 and {len(available_models)}")
                selected_idx = None
        except ValueError:
            print("Please enter a valid number")
    
    selected_lang, selected_model_path = available_models[selected_idx]
    print(f"\nSelected language: {selected_lang.upper()} using model at {selected_model_path}\n")
    
    # Load the selected model
    try:
        print(f"Loading {selected_lang.upper()} model...")
        model = Model(selected_model_path)
        recognizer = KaldiRecognizer(model, 16000)
        print(f"{selected_lang.upper()} model loaded successfully")
    except Exception as e:
        print(f"Error setting up Vosk model: {e}")
        exit(1)
    
    # Skip microphone setup - we only want to use WebSocket data
    print("WebSocket-only mode activated - ignoring PC microphone")
    stream = None
    mic = None
    
    print(f"\n Waiting for WebSocket audio from phone... (say 'stop' or 'arrêter' to exit)")
    print("Connect your phone to WebSocket at ws://YOUR_SERVER_IP:8765")
    print("\n=========== VOICE COMMANDS ===========")
    
    # Track last recognized text to avoid duplicates
    last_recognized_text = ""
    
    # Main recognition loop
    while True:
        try:
            # Only get data from WebSocket
            try:
                # Use a timeout to avoid blocking indefinitely
                data = audio_queue.get(timeout=0.5)
                
                # Only warn about small packets when debugging
                if len(data) < 100:
                    pass  # Removed noisy debug message
                
                # Process the audio only if it's not empty
                if len(data) == 0:
                    continue
                
                # Optional audio preprocessing
                data = preprocess_audio(data)
                
                # Process with recognizer
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    
                    # Only process if we have text
                    if 'text' in result and result['text']:
                        command = result['text']
                        
                        # Avoid duplicate recognitions
                        if command != last_recognized_text and command.strip():
                            print(f"\n Recognized: '{command}'")
                            execute_command(command)
                            last_recognized_text = command
                
                # Check for partial results (show these less prominently)
                partial = json.loads(recognizer.PartialResult())
                if 'partial' in partial and partial['partial']:
                    # Only show partial results that are different and substantial
                    partial_text = partial['partial']
                    if len(partial_text) > 3 and partial_text != last_recognized_text:
                        # Use a carriage return to allow overwriting this line with final result
                        print(f"\r Hearing: {partial_text}", end="", flush=True)
                
            except queue.Empty:
                # Just wait for more WebSocket data
                continue
                
        except Exception as e:
            print(f"Error in recognition loop: {e}")
            import traceback
            traceback.print_exc()
            continue

except KeyboardInterrupt:
    print("\nKeyboard interrupt received, exiting...")
except Exception as e:
    print(f"\nUnhandled error occurred: {e}")
    import traceback
    traceback.print_exc()
finally:
    print("\nCleaning up resources...")
    try:
        # Clean up audio resources if they exist
        if 'stream' in locals() and stream is not None:
            stream.stop_stream()
            stream.close()
        if 'mic' in locals() and mic is not None:
            mic.terminate()
        
        print("WebSocket server will terminate with main program")
    except Exception as e:
        print(f"Error during cleanup: {e}")
    
    print("Press Enter to exit...")
    input()
