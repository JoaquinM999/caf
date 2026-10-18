// Caf Voice Settings Page (settings.html -> Notch -> Caf · Voz).
// Replaces « OK Coucou » with Caf (Gemini Live) while maintaining zero upstream conflict.

import { h, clear } from "../../views/dom";
import { Bridge } from "../../core/bridge";
import type { HubContext } from "../shell";
import { button, card, divider, label, row, toggle } from "../ui";

const GEMINI_SECRET_KEY = "caf-api-key";
const KEY_STORE = navigator.userAgent.includes("Windows")
  ? "Windows Credential Manager"
  : "Secret Service (GNOME Keyring, KWallet)";

interface CafConfigResponse {
  voice: string;
  model?: string;
  profile: string;
  wake_enabled: boolean;
  headphones: boolean;
  available_voices: string[];
}

const LIVE_MODELS: { id: string; name: string; desc: string }[] = [
  { id: "gemini-3.8-live", name: "Gemini 3.8 Live (Predeterminado)", desc: "Máxima velocidad, latencia mínima y conversación de audio natural fluida" },
  { id: "gemini-2.5-flash", name: "Gemini 2.5 Flash Live", desc: "Ultrarrápido, versátil y equilibrado" },
  { id: "gemini-2.5-pro", name: "Gemini 2.5 Pro Live", desc: "Máxima capacidad analítica para razonamiento profundo y herramientas complejas" },
  { id: "gemini-2.0-flash", name: "Gemini 2.0 Flash Live", desc: "Ligero y de respuesta inmediata" },
];

interface AudioDevicesResponse {
  inputs?: { index: number; name: string }[];
  outputs?: { index: number; name: string }[];
  input_devices?: { index: number; name: string }[];
  output_devices?: { index: number; name: string }[];
  current_input_index?: number | null;
  current_output_index?: number | null;
  headphones?: boolean;
  auto_headphones?: boolean;
  detected_headphones?: { input: number | null; output: number | null };
}

const VOICES: { id: string; name: string; desc: string; gender: "female" | "male" }[] = [
  { id: "Aoede", name: "Aoede (Recomendada)", desc: "Femenina · Cálida, empática y muy natural", gender: "female" },
  { id: "Kore", name: "Kore", desc: "Femenina · Clara, suave y articulada", gender: "female" },
  { id: "Leda", name: "Leda", desc: "Femenina · Expresiva, dinámica y amigable", gender: "female" },
  { id: "Zephyr", name: "Zephyr", desc: "Femenina · Calma, equilibrada y precisa", gender: "female" },
  { id: "Puck", name: "Puck", desc: "Masculina · Enérgica, joven y alegre", gender: "male" },
  { id: "Charon", name: "Charon", desc: "Masculina · Profunda, grave y pausada", gender: "male" },
  { id: "Fenrir", name: "Fenrir", desc: "Masculina · Firme, formal y segura", gender: "male" },
  { id: "Orus", name: "Orus", desc: "Masculina · Dinámica, directa y moderna", gender: "male" },
];

export async function voicePage(page: HTMLElement, ctx: HubContext) {
  page.append(
    ctx.hero(
      "voice",
      "Caf · Asistente de Voz",
      "Tu copiloto conversacional con Gemini Live. Di 'Caf' para hablar, abrir programas, poner música y controlar tu PC."
    )
  );

  let config: CafConfigResponse = {
    voice: "Aoede",
    profile: "amiguito",
    wake_enabled: true,
    headphones: false,
    available_voices: ["Aoede", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Zephyr"],
  };

  try {
    const res = await fetch("http://127.0.0.1:8000/config");
    if (res.ok) config = await res.json();
  } catch {}

  // ── Sección 1: Estado y Escucha ───────────────────────────────────────────
  page.append(label("Activación por Voz y Teclado"));

  const wakeToggle = toggle(config.wake_enabled, async (enabled) => {
    config.wake_enabled = enabled;
    try {
      await fetch("http://127.0.0.1:8000/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ wake_enabled: enabled }),
      });
    } catch {}
  });

  const wakeRow = row(
    "Escuchar palabra de activación 'Caf'",
    "El micrófono detecta cuando decís 'Caf' en tu propia PC mediante Vosk (sin enviar audio a internet hasta que lo llamás).",
    wakeToggle
  );

  const statusNote = h(
    "div",
    { class: "hub-note", style: "display: flex; align-items: center; justify-content: space-between;" },
    h(
      "span",
      {},
      "Atajo de teclado manual: presioná ",
      h("kbd", { style: "padding: 2px 6px; background: rgba(255,255,255,0.1); border-radius: 4px;" }, "F8"),
      " para despertar a Caf al instante sin hablar."
    ),
    button(
      "Despertar ahora",
      async () => {
        try {
          const ws = new WebSocket("ws://127.0.0.1:8000/ws");
          ws.onopen = () => {
            ws.send(JSON.stringify({ action: "despertar" }));
            setTimeout(() => ws.close(), 300);
          };
        } catch {}
      },
      "",
      true
    )
  );

  page.append(card(wakeRow, divider(), statusNote));

  // ── Sección 2: Única API Key (Google Gemini) ──────────────────────────────
  page.append(label("Credenciales de IA"));

  const keyBox = h("div", { style: "display: flex; gap: 8px; align-items: center;" });
  const keyPresent = Boolean(
    (await Bridge.secretPresent(GEMINI_SECRET_KEY)) || (await Bridge.secretPresent("google-api-key"))
  );

  const drawKeyBox = (hasKey: boolean) => {
    clear(keyBox);
    if (hasKey) {
      keyBox.append(
        h("span", {
          class: "hub-badge on",
          style: "font-size: 12px; color: var(--hub-green);",
          text: `✓ Clave guardada en ${KEY_STORE}`,
        }),
        button(
          "Cambiar clave",
          () => {
            void Bridge.secretClear(GEMINI_SECRET_KEY);
            void Bridge.secretClear("google-api-key");
            void drawKeyBox(false);
          },
          "",
          true
        )
      );
      return;
    }
    const input = h("input", {
      class: "hub-input",
      type: "password",
      placeholder: "Pegá tu GEMINI_API_KEY (AIza...)",
      autocomplete: "off",
      spellcheck: "false",
      style: "width: 260px;",
    }) as HTMLInputElement;

    const save = button(
      "Guardar clave",
      async () => {
        const val = input.value.trim();
        if (!val) return;
        await Bridge.secretSet(GEMINI_SECRET_KEY, val);
        try {
          await fetch("http://127.0.0.1:8000/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ api_key: val }),
          });
        } catch {}
        void drawKeyBox(true);
      },
      "primary",
      true
    );

    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") save.click();
    });
    keyBox.append(input, save);
  };

  void drawKeyBox(keyPresent);

  const apiCard = card(
    row(
      "API Key de Gemini",
      "Una sola clave de Gemini Live reemplaza a Claude y ElevenLabs con razonamiento y voz humana en tiempo real.",
      keyBox
    )
  );
  page.append(apiCard);

  // ── Sección 3: Selector de Modelo de Gemini Live ───────────────────────────
  page.append(label("Modelo de Gemini Live"));

  const modelList = h("div", { style: "display: flex; flex-direction: column; gap: 6px; padding: 10px 14px;" });
  const modelItemMap = new Map<string, { root: HTMLElement; badge: HTMLElement }>();

  function selectModelInUI(modelId: string) {
    for (const [id, item] of modelItemMap) {
      const isSel = id.toLowerCase() === modelId.toLowerCase();
      item.root.style.borderColor = isSel ? "var(--hub-green)" : "rgba(255,255,255,0.08)";
      item.root.style.background = isSel ? "rgba(34, 197, 94, 0.1)" : "rgba(255,255,255,0.03)";
      item.badge.textContent = isSel ? "✓ Activo" : "Elegir";
      item.badge.style.color = isSel ? "var(--hub-green)" : "var(--dim-4)";
    }
  }

  for (const m of LIVE_MODELS) {
    const isSelected = (config.model || "gemini-3.8-live").toLowerCase() === m.id.toLowerCase();
    const badge = h("span", {
      style: `font-size: 12px; font-weight: 500; color: ${isSelected ? "var(--hub-green)" : "var(--dim-4)"};`,
      text: isSelected ? "✓ Activo" : "Elegir",
    });

    const item = h(
      "div",
      {
        class: `hub-model-item ${isSelected ? "selected" : ""}`,
        style: `display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-radius: 8px; border: 1px solid ${
          isSelected ? "var(--hub-green)" : "rgba(255,255,255,0.08)"
        }; background: ${isSelected ? "rgba(34, 197, 94, 0.1)" : "rgba(255,255,255,0.03)"}; cursor: pointer; transition: all 0.2s;`,
      },
      h(
        "div",
        {},
        h("div", { style: "font-weight: 600; font-size: 13px;", text: m.name }),
        h("div", { style: "font-size: 11px; color: var(--dim-3); margin-top: 2px;", text: m.desc })
      ),
      badge
    );

    modelItemMap.set(m.id, { root: item, badge });

    item.onclick = async () => {
      config.model = m.id;
      selectModelInUI(m.id);
      try {
        await fetch("http://127.0.0.1:8000/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ model: m.id }),
        });
      } catch {}
    };

    modelList.append(item);
  }

  page.append(card(modelList));

  // ── Sección 4: Selector de Voces Nativas de Gemini ─────────────────────────
  page.append(label("Voz de Caf (Gemini Live)"));

  const voiceList = h("div", { style: "display: flex; flex-direction: column; gap: 6px; padding: 10px 14px;" });
  const voiceItemMap = new Map<string, { root: HTMLElement; badge: HTMLElement }>();

  function selectVoiceInUI(voiceId: string) {
    for (const [id, item] of voiceItemMap) {
      const isSel = id.toLowerCase() === voiceId.toLowerCase();
      item.root.style.borderColor = isSel ? "var(--hub-green)" : "rgba(255,255,255,0.08)";
      item.root.style.background = isSel ? "rgba(34, 197, 94, 0.1)" : "rgba(255,255,255,0.03)";
      item.badge.textContent = isSel ? "✓ Activa" : "Elegir";
      item.badge.style.color = isSel ? "var(--hub-green)" : "var(--dim-4)";
    }
  }

  for (const v of VOICES) {
    const isSelected = (config.voice || "Aoede").toLowerCase() === v.id.toLowerCase();
    const badge = h("span", {
      style: `font-size: 12px; font-weight: 500; color: ${isSelected ? "var(--hub-green)" : "var(--dim-4)"};`,
      text: isSelected ? "✓ Activa" : "Elegir",
    });

    const item = h(
      "div",
      {
        class: `hub-voice-item ${isSelected ? "selected" : ""}`,
        style: `display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-radius: 8px; border: 1px solid ${
          isSelected ? "var(--hub-green)" : "rgba(255,255,255,0.08)"
        }; background: ${isSelected ? "rgba(34, 197, 94, 0.1)" : "rgba(255,255,255,0.03)"}; cursor: pointer; transition: all 0.2s;`,
      },
      h(
        "div",
        {},
        h("div", { style: "font-weight: 600; font-size: 13px;", text: v.name }),
        h("div", { style: "font-size: 11px; color: var(--dim-3); margin-top: 2px;", text: v.desc })
      ),
      badge
    );

    voiceItemMap.set(v.id, { root: item, badge });

    item.onclick = async () => {
      config.voice = v.id;
      selectVoiceInUI(v.id);
      try {
        await fetch("http://127.0.0.1:8000/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ voice: v.id }),
        });
      } catch {}
    };

    voiceList.append(item);
  }

  page.append(card(voiceList));

  // ── Sección 4: Dispositivos de Audio ──────────────────────────────────────
  page.append(label("Entrada y Salida de Audio"));

  const micSelect = h("select", {
    style:
      "background: #141518; color: var(--ink); border: 1px solid rgba(255,255,255,0.12); border-radius: 6px; padding: 6px 10px; font-size: 12px; outline: none; cursor: pointer; max-width: 320px;",
  }) as HTMLSelectElement;

  const speakerSelect = h("select", {
    style:
      "background: #141518; color: var(--ink); border: 1px solid rgba(255,255,255,0.12); border-radius: 6px; padding: 6px 10px; font-size: 12px; outline: none; cursor: pointer; max-width: 320px;",
  }) as HTMLSelectElement;

  let autoHeadphonesState = true;
  const autoHpToggle = toggle(autoHeadphonesState, (enabled) => {
    autoHeadphonesState = enabled;
    if (enabled) {
      applyHeadphonesPriority();
    }
  });

  const saveFeedback = h("span", {
    style: "font-size: 12px; color: var(--hub-green); margin-right: 10px; opacity: 0; transition: opacity 0.2s;",
    text: "✓ Dispositivos guardados",
  });

  async function saveAudioDevices() {
    const inVal = parseInt(micSelect.value, 10);
    const outVal = parseInt(speakerSelect.value, 10);
    const payload = {
      input_device_index: inVal >= 0 ? inVal : null,
      output_device_index: outVal >= 0 ? outVal : null,
      input_device: inVal >= 0 ? inVal : null,
      output_device: outVal >= 0 ? outVal : null,
      auto_headphones: autoHeadphonesState,
      headphones: /airpods|auricular|headphone|headset|buds/i.test(
        speakerSelect.options[speakerSelect.selectedIndex]?.text ?? ""
      ),
    };
    try {
      await fetch("http://127.0.0.1:8000/audio/devices", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      saveFeedback.style.opacity = "1";
      setTimeout(() => {
        saveFeedback.style.opacity = "0";
      }, 2500);
    } catch {}
  }

  const saveBtn = button("Guardar cambios", () => void saveAudioDevices(), "primary", true);

  let rawAudioData: AudioDevicesResponse | null = null;

  function applyHeadphonesPriority() {
    if (!rawAudioData) return;
    const outputs = rawAudioData.outputs || rawAudioData.output_devices || [];
    const inputs = rawAudioData.inputs || rawAudioData.input_devices || [];
    const hpOut = outputs.find((o) => /airpods|auricular|headphone|headset|buds/i.test(o.name));
    const hpIn = inputs.find((i) => /airpods|auricular|headphone|headset|buds/i.test(i.name));
    if (hpOut) {
      speakerSelect.value = String(hpOut.index);
    }
    if (hpIn) {
      micSelect.value = String(hpIn.index);
    }
  }

  try {
    const res = await fetch("http://127.0.0.1:8000/audio/devices");
    if (res.ok) {
      const data: AudioDevicesResponse = await res.json();
      rawAudioData = data;
      autoHeadphonesState = data.auto_headphones ?? true;

      const inputs = data.inputs || data.input_devices || [];
      const outputs = data.outputs || data.output_devices || [];

      clear(micSelect);
      micSelect.append(h("option", { value: "-1", text: "🎙️ Micrófono Predeterminado del Sistema" }));
      for (const m of inputs) {
        const opt = h("option", { value: String(m.index), text: m.name }) as HTMLOptionElement;
        if (data.current_input_index === m.index) opt.selected = true;
        micSelect.append(opt);
      }

      clear(speakerSelect);
      speakerSelect.append(h("option", { value: "-1", text: "🔊 Altavoz Predeterminado del Sistema" }));
      for (const s of outputs) {
        const opt = h("option", { value: String(s.index), text: s.name }) as HTMLOptionElement;
        if (data.current_output_index === s.index) opt.selected = true;
        speakerSelect.append(opt);
      }

      if (autoHeadphonesState && data.current_output_index == null) {
        applyHeadphonesPriority();
      }
    }
  } catch {}

  const audioCard = card(
    row(
      "Priorizar auriculares automáticamente",
      "Si detecta AirPods, auriculares Bluetooth o headset conectados, enruta la voz y el micrófono a ellos.",
      autoHpToggle
    ),
    divider(),
    row("Micrófono de entrada", "Dispositivo usado para capturar tu voz al decir 'Caf'.", micSelect),
    divider(),
    row("Altavoz / Auriculares de salida", "Dispositivo por el cual suena la voz de Caf.", speakerSelect),
    divider(),
    h(
      "div",
      {
        class: "hub-note",
        style: "display: flex; justify-content: flex-end; align-items: center; padding-top: 4px;",
      },
      saveFeedback,
      saveBtn
    )
  );
  page.append(audioCard);

  // ── Sección 5: Memoria Persistente de Caf ──────────────────────────────────
  page.append(label("Memoria Persistente de Caf (memoria.json)"));

  const memoryContainer = h("div", {
    style: "display: flex; flex-direction: column; gap: 8px; padding: 12px 14px;",
  });

  const renderMemories = async () => {
    clear(memoryContainer);
    let recuerdos: string[] = [];
    try {
      const res = await fetch("http://127.0.0.1:8000/memory");
      if (res.ok) {
        const data = await res.json();
        recuerdos = data.recuerdos || [];
      }
    } catch {}

    if (recuerdos.length === 0) {
      memoryContainer.append(
        h("div", {
          class: "hub-note",
          style: "padding: 6px 0;",
          text: "No hay recuerdos guardados aún en memoria.json.",
        })
      );
    } else {
      for (const r of recuerdos) {
        const memRow = h(
          "div",
          {
            style:
              "display: flex; align-items: center; justify-content: space-between; gap: 10px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); padding: 7px 10px; border-radius: 6px;",
          },
          h("span", { style: "font-size: 12px; color: var(--ink); flex: 1;", text: `• ${r}` }),
          button(
            "Olvidar",
            async () => {
              try {
                await fetch("http://127.0.0.1:8000/memory", {
                  method: "DELETE",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ recuerdo: r }),
                });
                void renderMemories();
              } catch {}
            },
            "danger",
            true
          )
        );
        memoryContainer.append(memRow);
      }
    }

    const addBox = h("div", { style: "display: flex; gap: 8px; margin-top: 6px;" });
    const addInput = h("input", {
      class: "hub-input",
      placeholder: "Agregar instrucción o recuerdo (ej. 'Mi nombre es Joaquín')...",
      style: "flex: 1;",
    }) as HTMLInputElement;

    const addBtn = button(
      "Guardar recuerdo",
      async () => {
        const val = addInput.value.trim();
        if (!val) return;
        try {
          await fetch("http://127.0.0.1:8000/memory", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ recuerdo: val }),
          });
          addInput.value = "";
          void renderMemories();
        } catch {}
      },
      "primary",
      true
    );

    addInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") addBtn.click();
    });

    addBox.append(addInput, addBtn);
    memoryContainer.append(addBox);
  };

  void renderMemories();
  page.append(card(memoryContainer));
}
