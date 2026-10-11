export class CafClient {
  private ws: WebSocket | null = null;
  private reconnectTimer: number | null = null;
  private attempts = 0;
  private onStateChange: (state: string, extra?: any) => void;
  private onTranscription: (role: string, text: string) => void;

  constructor(
    onStateChange: (state: string, extra?: any) => void,
    onTranscription: (role: string, text: string) => void
  ) {
    this.onStateChange = onStateChange;
    this.onTranscription = onTranscription;
  }

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) return;
    try {
      this.ws = new WebSocket("ws://127.0.0.1:8000/ws");
    } catch {
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      console.log("CafClient connected.");
      this.attempts = 0;
      if (this.reconnectTimer) {
        window.clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
      this.onStateChange("conectado");
    };

    this.ws.onmessage = (event) => {
      if (typeof event.data === "string") {
        try {
          const data = JSON.parse(event.data);
          if (data.estado) {
            this.onStateChange(data.estado, data.detalle);
          }
          if (data.modo) {
            this.onStateChange(data.modo);
          }
          if (data.transcripcion) {
            this.onTranscription(data.transcripcion.rol, data.transcripcion.texto);
          }
        } catch (e) {
          console.error("CafClient parse error:", e);
        }
      }
    };

    this.ws.onclose = () => {
      this.ws = null;
      this.onStateChange("desconectado");
      this.scheduleReconnect();
    };

    this.ws.onerror = (e) => {
      console.warn("CafClient error:", e);
    };
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.attempts++;
    const delay = Math.min(1000 * Math.pow(1.3, this.attempts), 6000);
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  sendPtt(down: boolean) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: "ptt", down }));
    }
  }

  sendText(text: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: "hablar", text }));
    }
  }

  wake() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: "despertar" }));
    }
  }

  sleep() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: "dormir" }));
    }
  }

  toggle() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: "despertar" }));
    }
  }

  mute(muted: boolean) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: muted ? "silenciar" : "activar" }));
    }
  }

  changeProfile(profile: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: "cambiar_perfil", profile }));
    }
  }
}
