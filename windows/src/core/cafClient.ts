import { State } from "./state";
import { Sound } from "./sound";

export class CafClient {
  private ws: WebSocket | null = null;
  private reconnectTimer: number | null = null;
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
    if (this.ws) return;
    this.ws = new WebSocket("ws://127.0.0.1:8000/ws");

    this.ws.onopen = () => {
      console.log("CafClient connected.");
      if (this.reconnectTimer) {
        window.clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
    };

    this.ws.onmessage = (event) => {
      if (typeof event.data === "string") {
        try {
          const data = JSON.parse(event.data);
          if (data.estado) {
            this.onStateChange(data.estado, data.detalle);
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
      console.log("CafClient disconnected. Reconnecting in 2s...");
      this.ws = null;
      this.reconnectTimer = window.setTimeout(() => this.connect(), 2000);
    };

    this.ws.onerror = (e) => {
      console.error("CafClient error:", e);
    };
  }

  sendText(text: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: "hablar", text }));
    }
  }

  changeProfile(profile: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: "cambiar_perfil", profile }));
    }
  }
}
