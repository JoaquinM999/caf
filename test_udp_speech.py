import socket
import time

udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

with open(r"C:\Users\Joako\OneDrive\Escritorio\Coucou\test_speech.pcm", "rb") as f:
    speech_data = f.read()

# Generate 3 seconds of silence
silence = b"\x00" * (16000 * 3 * 2)

print("Sending speech...")
chunk_size = 4000 # 125ms per chunk
for i in range(0, len(speech_data), chunk_size):
    udp_sock.sendto(speech_data[i:i+chunk_size], ("127.0.0.1", 4000))
    time.sleep(0.125)

print("Sending 3s of silence (to trigger VAD)...")
for i in range(0, len(silence), chunk_size):
    udp_sock.sendto(silence[i:i+chunk_size], ("127.0.0.1", 4000))
    time.sleep(0.125)

print("Done.")
