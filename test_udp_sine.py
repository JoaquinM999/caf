import socket
import time
import struct
import math

udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Generate 2 seconds of a 440Hz sine wave (16000Hz, 16-bit PCM)
sine_wave = b""
for i in range(16000 * 2):
    sample = int(32767 * math.sin(2 * math.pi * 440 * (i / 16000.0)))
    sine_wave += struct.pack('<h', sample)

# Generate 3 seconds of silence
silence = b"\x00" * (16000 * 3 * 2)

print("Sending 2s of tone...")
chunk_size = 4000 # 125ms per chunk
for i in range(0, len(sine_wave), chunk_size):
    udp_sock.sendto(sine_wave[i:i+chunk_size], ("127.0.0.1", 4000))
    time.sleep(0.125)

print("Sending 3s of silence...")
for i in range(0, len(silence), chunk_size):
    udp_sock.sendto(silence[i:i+chunk_size], ("127.0.0.1", 4000))
    time.sleep(0.125)

print("Done.")
