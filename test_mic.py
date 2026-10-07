import socket
import time
import wave
import io
import urllib.request
import json
import base64

def generate_tts_pcm():
    # Use a public TTS API or a known base64 string to get a PCM audio
    # For simplicity, here is a base64 of a 16kHz 16-bit PCM saying "hola"
    # Actually, generating it via edge-tts is better, but maybe edge-tts is not installed.
    # Let's just create a generic payload or use python's pyttsx3 if available?
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.save_to_file("Hola Gemini, dime un numero del 1 al 10", "test.wav")
        engine.runAndWait()
        
        # convert to 16kHz 16bit PCM
        import subprocess
        subprocess.run(["ffmpeg", "-y", "-i", "test.wav", "-ar", "16000", "-ac", "1", "-f", "s16le", "test.pcm"])
        with open("test.pcm", "rb") as f:
            return f.read()
    except Exception as e:
        print("Failed to use pyttsx3:", e)
        return b""

def send_udp_audio():
    pcm_data = generate_tts_pcm()
    if not pcm_data:
        print("No PCM data to send.")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("Sending audio to Rust UDP port 4000...")
    
    # Send in chunks of 4000 bytes (125ms)
    chunk_size = 4000
    for i in range(0, len(pcm_data), chunk_size):
        chunk = pcm_data[i:i+chunk_size]
        sock.sendto(chunk, ("127.0.0.1", 4000))
        time.sleep(0.125)
    print("Finished sending audio.")

if __name__ == "__main__":
    send_udp_audio()
