import { invoke } from "@tauri-apps/api/core";
import { Bridge, IS_TAURI, onEvent } from "./bridge";
import type { PillState } from "./flow";
import { handleIslandVoiceAsk } from "../island/voice";

export interface VoicePillView {
  phase: "listening" | "thinking" | "speaking";
  heard: string;
  answer: string;
}

export class CafClient {
  private ws: WebSocket | null = null;
  private reconnectTimer: number | null = null;
  private attempts = 0;
  private onStateChange: (state: string, extra?: any) => void;
  private onTranscription: (role: string, text: string) => void;
  private lastAnswer = "";
  private currentPhase: "listening" | "thinking" | "speaking" | "idle" = "idle";
  private dictatingMuted = false;

  constructor(
    onStateChange: (state: string, extra?: any) => void,
    onTranscription: (role: string, text: string) => void
  ) {
    this.onStateChange = onStateChange;
    this.onTranscription = onTranscription;
    this.listenFlowDictation();
  }

  private listenFlowDictation() {
    if (!IS_TAURI) return;
    void onEvent<PillState>("pill-state", (s) => {
      const isDictating = s.phase === "listening" || s.phase === "locked";
      if (isDictating && !this.dictatingMuted) {
        this.dictatingMuted = true;
        this.mute(true);
      } else if (!isDictating && this.dictatingMuted) {
        this.dictatingMuted = false;
        this.mute(false);
      }
    });
  }

  private updateVoicePill(view: VoicePillView | null) {
    if (!IS_TAURI) return;
    const text = view ? JSON.stringify(view) : null;
    void invoke("voice_done", { id: 0, text }).catch(() => {});
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

          // Island RPC request from backend (pills, info, spotify_volume)
          if (data.island_ask) {
            this.handleIslandAsk(data.island_ask);
            return;
          }

          if (data.estado) {
            const st = data.estado;
            this.onStateChange(st, data.detalle);
            if (st === "escuchando") {
              this.currentPhase = "listening";
              this.updateVoicePill({ phase: "listening", heard: "", answer: "" });
            } else if (st === "pensando" || st === "ejecutando_herramienta") {
              this.currentPhase = "thinking";
              this.updateVoicePill({ phase: "thinking", heard: "", answer: "" });
            } else if (st === "hablando") {
              this.currentPhase = "speaking";
              this.updateVoicePill({ phase: "speaking", heard: "", answer: this.lastAnswer });
            } else if (st === "dormido" || st === "desconectado") {
              this.currentPhase = "idle";
              this.lastAnswer = "";
              this.updateVoicePill(null);
            }
          }

          if (data.modo) {
            this.onStateChange(data.modo);
            if (data.modo === "dormido") {
              this.currentPhase = "idle";
              this.updateVoicePill(null);
            }
          }

          if (data.transcripcion) {
            const { rol, texto } = data.transcripcion;
            this.onTranscription(rol, texto);
            if (rol === "usuario" || rol === "user") {
              this.lastAnswer = "";
              this.currentPhase = "thinking";
              // Solo se escribe en la cápsula lo que Caf dice
              this.updateVoicePill({ phase: "thinking", heard: "", answer: "" });
            } else if (rol === "caf" || rol === "assistant") {
              this.lastAnswer = texto;
              this.currentPhase = "speaking";
              this.updateVoicePill({ phase: "speaking", heard: "", answer: this.lastAnswer });
            }
          }
        } catch (e) {
          console.error("CafClient parse error:", e);
        }
      }
    };

    this.ws.onclose = () => {
      this.ws = null;
      this.currentPhase = "idle";
      this.updateVoicePill(null);
      this.onStateChange("desconectado");
      this.scheduleReconnect();
    };

    this.ws.onerror = (e) => {
      console.warn("CafClient error:", e);
    };
  }

  private handleIslandAsk(ask: { id: number; kind: "pills" | "info" | "spotify_volume" | "spotify_control"; input?: any }) {
    let result = "";
    try {
      if (ask.kind === "spotify_volume") {
        const vol = typeof ask.input?.volume === "number" ? ask.input.volume : 50;
        void Bridge.spotifyControl("volume", vol);
        result = "done";
      } else if (ask.kind === "spotify_control") {
        const action = (ask.input?.action as any) || "playPause";
        const val = typeof ask.input?.value === "number" ? ask.input.value : undefined;
        void Bridge.spotifyControl(action, val);
        result = "done";
      } else {
        result = handleIslandVoiceAsk(ask.kind as "pills" | "info", ask.input);
      }
    } catch (err) {
      result = `error: ${String(err)}`;
    }

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: "island_reply", id: ask.id, result }));
    }
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
    if (this.currentPhase !== "idle") {
      this.sleep();
    } else {
      this.wake();
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
