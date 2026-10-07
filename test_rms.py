import socket
import struct

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", 4001)) # Just to test RMS locally without breaking tauri
print("Listening...")
while True:
    data, addr = sock.recvfrom(8000)
    samples = struct.unpack(f'<{len(data)//2}h', data)
    rms = int((sum(s*s for s in samples) / len(samples)) ** 0.5)
    print(f"RMS: {rms}")
