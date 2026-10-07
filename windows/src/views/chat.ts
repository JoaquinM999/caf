// Chat view — DOM port of PromptView / ChatBubble / TypingDotsView from
// IslandViewContent.swift.

import { h, svg, clear } from "./dom";
import { ICONS } from "./icons";
import { Bridge, type ChatContext } from "../core/bridge";
import { Sound } from "../core/sound";
import { State, type ChatMessage } from "../core/state";
import type { ViewHost } from "./views";
import { listen } from "@tauri-apps/api/event";

let nextId = 1;

function bubble(message: ChatMessage): HTMLElement {
  if (message.role === "user") {
    return h(
      "div",
      { class: "chat-row user" },
      h("div", { class: "bubble", text: message.content }),
    );
  }
  return h("div", { class: "chat-row" }, h("div", { class: "reply", text: message.content }));
}

function typingDots(): HTMLElement {
  return h(
    "div",
    { class: "chat-row" },
    h("div", { class: "typing" }, h("i"), h("i"), h("i")),
  );
}

/** The coloured chip showing what the question is about (a dropped file). */
function contextChip(label: string): HTMLElement {
  const chip = h("div", { class: "chip" }, h("i", { class: "chip-dot" }), h("span", { text: label }));
  requestAnimationFrame(() => chip.classList.add("settled"));
  return chip;
}

export function buildPrompt(onHeightChange: () => void): ViewHost {
  const chipRow = h("div", { class: "chip-row" });
  const log = h("div", { class: "chat-log" });
  const input = h("input", {
    type: "text",
    class: "chat-input",
    placeholder: "Ask me anything…",
    spellcheck: "false",
  }) as HTMLInputElement;

  const send = h("button", { class: "send-btn", title: "Send" }, svg(ICONS.arrowUp, 11));
  const voice = h("button", { class: "send-btn", title: "Voice dictation", style: "margin-right: 4px;" }, svg(ICONS.mic, 12));
  const bar = h("div", { class: "chat-bar" }, input, voice, send);

  const el = h(
    "div",
    { class: "view" },
    h("div", { class: "card wash chat-card" }, h("div", { class: "chat-body" }, chipRow, log, bar)),
  );

  let sending = false;
  let renderedCount = -1;

  async function submit() {
    const query = input.value.trim();
    if (!query || sending) return;
    input.value = "";
    sending = true;
    Sound.play("send");

    State.chatHistory.push({ id: nextId++, role: "user", content: query });
    State.stateOverride = "thinking";
    State.notify();
    onHeightChange();

    const file = State.droppedFile;
    const context: ChatContext | null =
      State.chatHistory.length === 1 && file ? { kind: "file", name: file.name, path: file.path } : null;

    const isAmiguito = State.focusTask?.id === "integration_amiguito";
    const persona = isAmiguito ? "amiguito" : "coucou";

    try {
      const reply = await Bridge.chatSend(query, context, persona);
      State.chatHistory.push({ id: nextId++, role: "assistant", content: reply.text });
      State.stateOverride = null;
      Sound.play("finish");
      
      if (persona === "amiguito") {
          Bridge.speak(reply.text);
      }
    } catch (err) {
      State.stateOverride = null;
      State.noteMessage = String(err).replace(/^Error:\s*/, "");
      State.view = "note";
      Sound.play("error");
    } finally {
      sending = false;
      State.notify();
      onHeightChange();
      input.focus();
    }
  }

  send.addEventListener("click", () => void submit());
  voice.addEventListener("click", () => { Bridge.wakeVoice(); });
  input.addEventListener("keydown", (e) => {
    if ((e as KeyboardEvent).key === "Enter") {
      e.preventDefault();
      void submit();
    }
    e.stopPropagation(); // Escape closes the island, not the chat
  });

  // Escuchar a Python mediante Tauri events
  listen<string>("voice-input", (event) => {
      // Activar Amiguito si está disponible
      const amiguito = State.tasks.find(t => t.id === "integration_amiguito");
      if (amiguito) {
          State.setFocus(amiguito.id);
      }
      input.value = event.payload;
      void submit();
  });

  listen<string>("gemini-reply", (event) => {
      State.chatHistory.push({ id: nextId++, role: "assistant", content: event.payload });
      State.notify();
      onHeightChange();
  });

  listen<string>("voice-status", (event) => {
      const st = event.payload;
      State.voiceStatus = st;
      State.notify();
      
      // Auto-focus Amiguito if a live call starts
      if (st === "Live" || st === "Te estoy escuchando..." || st === "Gemini está pensando..." || st === "Gemini está hablando..." || st === "Esperando tu voz...") {
          const amiguito = State.tasks.find(t => t.id === "integration_amiguito");
          if (amiguito && State.focusTask?.id !== amiguito.id) {
              State.setFocus(amiguito.id);
          }
      }

      if (st === "Escuchando" || st === "Te estoy escuchando..." || st === "Esperando tu voz..." || st === "Live") {
          input.placeholder = "🎙️ " + (st === "Live" ? "Conectando..." : st);
          voice.style.background = "rgba(239, 68, 68, 0.2)"; // rojito
          voice.style.animation = "pulse 1.5s infinite";
      } else if (st === "Procesando" || st === "Gemini está pensando...") {
          input.placeholder = "⏳ " + st;
          voice.style.background = "rgba(245, 158, 11, 0.2)"; // naranjita
          voice.style.animation = "pulse 1s infinite";
      } else if (st === "Ajustando") {
          input.placeholder = "Ajustando ruido...";
          voice.style.background = "rgba(107, 114, 128, 0.2)"; // gris
          voice.style.animation = "";
      } else if (st === "Gemini está hablando...") {
          input.placeholder = "🔊 " + st;
          voice.style.background = "rgba(168, 85, 247, 0.3)"; // violetita
          voice.style.animation = "pulse 0.5s infinite alternate";
      } else {
          // inactivo, hablando, error
          input.placeholder = "Ask me anything…";
          voice.style.background = "";
          voice.style.animation = "";
      }
  });

  return {
    el,
    sync() {
      const isAmiguito = State.focusTask?.id === "integration_amiguito";
      if (isAmiguito) {
        (el.querySelector(".card") as HTMLElement).style.setProperty("--wash", "rgba(168, 85, 247, 0.5)"); // violeta
      } else {
        (el.querySelector(".card") as HTMLElement).style.setProperty("--wash", "rgba(99, 102, 241, 0.5)"); // original azul
      }

      const file = State.droppedFile;
      const wantChip = file?.name ?? "";
      if (chipRow.dataset.label !== wantChip) {
        chipRow.dataset.label = wantChip;
        clear(chipRow);
        if (wantChip) chipRow.append(contextChip(wantChip));
      }

      const thinking = State.stateOverride === "thinking";
      const count = State.chatHistory.length + (thinking ? 0.5 : 0);
      if (count !== renderedCount) {
        renderedCount = count;
        clear(log);
        for (const m of State.chatHistory) log.append(bubble(m));
        if (thinking) log.append(typingDots());
        log.scrollTop = log.scrollHeight;
      }

      if (!voice.style.background) {
        if (isAmiguito) {
          input.placeholder = State.chatHistory.length === 0 ? "Control the PC..." : "Continue controlling...";
        } else {
          input.placeholder = State.chatHistory.length === 0 ? "Ask me anything…" : "Continue…";
        }
      }
      input.disabled = sending;
    },
    focus() {
      input.focus();
      input.select();
    },
  };
}
