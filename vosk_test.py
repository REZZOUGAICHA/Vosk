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
        
    import json
    import os
    import sys
    
    print("All dependencies loaded successfully")
    
    # Check if model folders exist
    model_path_en = "model_us"
    model_path_fr = "model_fr"
    
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
    
    # Microphone Setup
    print("Setting up microphone...")
    try:
        mic = pyaudio.PyAudio()
        
        # List available audio devices
        info = mic.get_host_api_info_by_index(0)
        num_devices = info.get('deviceCount')
        
        print("\n=== Available Microphones ===")
        for i in range(0, num_devices):
            if (mic.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
                print(f"Input Device ID {i}: {mic.get_device_info_by_host_api_device_index(0, i).get('name')}")
        
        # Let user select a device (optional)
        selected_device = None
        use_default = input("\nUse default microphone? (y/n): ").lower()
        if use_default != 'y':
            while selected_device is None:
                try:
                    device_input = input("Select microphone device ID: ")
                    selected_device = int(device_input)
                    if selected_device < 0 or selected_device >= num_devices:
                        print(f"Please enter a valid device ID between 0 and {num_devices-1}")
                        selected_device = None
                except ValueError:
                    print("Please enter a valid number")
        
        # Open the stream with the selected device (if any)
        if selected_device is not None:
            print(f"Using input device ID {selected_device}")
            stream = mic.open(
                format=pyaudio.paInt16, 
                channels=1, 
                rate=16000, 
                input=True, 
                input_device_index=selected_device,
                frames_per_buffer=8192
            )
        else:
            print("Using default input device")
            stream = mic.open(
                format=pyaudio.paInt16, 
                channels=1, 
                rate=16000, 
                input=True, 
                frames_per_buffer=8192
            )
        
        stream.start_stream()
        print("Microphone stream started successfully")
    except Exception as e:
        print(f"Error setting up the microphone: {e}")
        exit(1)
    
    print(f"\n🎙️ Speak in {selected_lang.upper()}... (say 'stop' or 'arrêter' to exit)")
    
    def execute_command(text):
        print(f"Processing command: '{text}'")
        
        if selected_lang == "en":
            # English commands
            if "door" in text:
                print("✅ Command: Opening the door")
            elif "start navigation" in text:
                print("✅ Command: NAV_START reception")
            elif "turn left" in text:
                print("🔄 Command: NAV_INSTRUCTION left")
            elif "turn right" in text:
                print("🔄 Command: NAV_INSTRUCTION right")
            elif "stop" in text:
                print("❌ Command: SYSTEM_STOP")
                os._exit(0)
            elif "detect obstacle" in text:
                print("🚨 Command: DETECT_SCAN")
            elif "battery" in text:
                print("🔋 Command: POWER_STATUS")
            elif "hello" in text:
                print("👋 Hello, How can I help you?")
            else:
                print("🤖 Command not recognized")
        
        elif selected_lang == "fr":
            # French commands
            if "porte" in text:
                print("✅ Command: Opening the door")
            elif "démarrez la navigation" in text:
                print("✅ Command: NAV_START reception")
            elif "tourne à gauche" in text:
                print("🔄 Command: NAV_INSTRUCTION left")
            elif "tourne à droite" in text:
                print("🔄 Command: NAV_INSTRUCTION right")
            elif "arrêtez" in text:
                print("❌ Command: SYSTEM_STOP")
                os._exit(0)
            elif "détecter obstacle" in text:
                print("🚨 Command: DETECT_SCAN")
            elif "batterie" in text:
                print("🔋 Command: POWER_STATUS")
            elif "bonjour" in text:
                print("👋 Hello, How can I help you?")
            else:
                print("🤖 Command not recognized")
    
    print("Starting recognition loop...")
    try:
        while True:
            try:
                data = stream.read(4096, exception_on_overflow=False)
                
                if len(data) == 0:
                    print("Warning: Empty audio data received")
                    continue
                
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    if 'text' in result and result['text']:
                        command = result['text']
                        print(f"You said: {command}")
                        execute_command(command)
                    else:
                        print("Received empty result")
                        
            except IOError as e:
                print(f"I/O error during audio processing: {e}")
                continue
            except Exception as e:
                print(f"Error in recognition loop: {e}")
                continue
    except KeyboardInterrupt:
        print("Keyboard interrupt received, exiting...")
    finally:
        print("Cleaning up resources...")
        try:
            stream.stop_stream()
            stream.close()
            mic.terminate()
            print("Audio resources released")
        except Exception as e:
            print(f"Error during cleanup: {e}")

except Exception as e:
    print(f"Unhandled error occurred: {e}")
    import traceback
    traceback.print_exc()
    
print("Press Enter to exit...")
input()  # This will keep the window open until you press Enter1