import socket
import wave

def record_udp_audio():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 4000))
    print("Listening on UDP 4000...")
    
    with wave.open("test_capture.wav", "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        
        for _ in range(40): # Record for 10 seconds (40 * 250ms)
            data, _ = sock.recvfrom(65535)
            wf.writeframes(data)
            print("Received packet size:", len(data))

if __name__ == "__main__":
    record_udp_audio()
