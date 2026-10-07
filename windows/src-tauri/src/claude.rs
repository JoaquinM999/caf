// Gemini API client — the same integration as ClaudeService.swift: multi-turn
// chat with files sent as text or inline media blocks.
//
// Everything happens here rather than in the island: the API key never leaves
// the Credential Manager, and file bytes never cross the IPC boundary.

use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::secrets;

const ENDPOINT: &str =
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent";
const MODELS_ENDPOINT: &str = "https://generativelanguage.googleapis.com/v1beta/models";
const MAX_TOKENS: u32 = 4096;
/// Text and code files are inlined; anything larger is skipped, as on macOS.
const MAX_INLINE_TEXT: u64 = 200_000;

pub const DEFAULT_MODEL: &str = "gemini-3-flash-preview";

#[derive(Default)]
pub struct Chat {
    /// Full multi-turn history, including tool_use / tool_result blocks.
    messages: Mutex<Vec<Value>>,
}

impl Chat {
    pub fn reset(&self) {
        self.messages.lock().unwrap().clear();
    }

    fn is_empty(&self) -> bool {
        self.messages.lock().unwrap().is_empty()
    }

    fn push(&self, message: Value) {
        self.messages.lock().unwrap().push(message);
    }

    fn pop(&self) {
        self.messages.lock().unwrap().pop();
    }

    fn snapshot(&self) -> Vec<Value> {
        self.messages.lock().unwrap().clone()
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "kind", rename_all = "camelCase")]
pub enum ChatContext {
    File { name: String, path: String },
    Window { app_name: String, title: String, url: Option<String> },
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ChatReply {
    pub text: String,
}

pub async fn transcribe_audio(audio_path: &str) -> Result<String, String> {
    let key = secrets::get("anthropic-api-key")
        .ok_or_else(|| "Falta API key de Gemini".to_string())?;
    
    let bytes = std::fs::read(audio_path).map_err(|e| e.to_string())?;
    use base64::{Engine as _, engine::general_purpose::STANDARD};
    let b64 = STANDARD.encode(&bytes);

    let client = reqwest::Client::new();
    let mut endpoint = reqwest::Url::parse(ENDPOINT).unwrap();
    endpoint.query_pairs_mut().append_pair("key", &key);

    let body = json!({
        "contents": [{
            "parts": [
                { "text": "Transcribe lo que se dice en este audio de voz con la mayor exactitud posible. Solo responde con la transcripción, sin agregar notas ni asistentencias. Ignora silencios." },
                {
                    "inlineData": {
                        "mimeType": "audio/wav",
                        "data": b64
                    }
                }
            ]
        }],
        "generationConfig": {
            "temperature": 0.0
        }
    });

    let res = client.post(endpoint).json(&body).send().await.map_err(|e| e.to_string())?;
    let text = res.text().await.unwrap_or_default();
    let value: Value = serde_json::from_str(&text).map_err(|e| e.to_string())?;

    if let Some(candidates) = value.get("candidates").and_then(Value::as_array) {
        if let Some(parts) = candidates.first().and_then(|c| c.get("content")).and_then(|c| c.get("parts")).and_then(Value::as_array) {
            if let Some(txt) = parts.first().and_then(|p| p.get("text")).and_then(Value::as_str) {
                return Ok(txt.trim().to_string());
            }
        }
    }
    Err("No se pudo transcribir el audio".to_string())
}
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GeminiModel {
    pub id: String,
    pub display_name: String,
}

/// One chat turn. Returns the assistant's text, or a message the island shows
/// in the note view.
pub async fn send(
    chat: &Chat,
    query: String,
    persona: Option<String>,
    context: Option<ChatContext>,
) -> Result<ChatReply, String> {
    let key = secrets::get("anthropic-api-key")
        .ok_or_else(|| "API key missing. Open settings.".to_string())?;

    let mut content: Vec<Value> = Vec::new();

    // File / window context rides along with the first message only, exactly
    // like ClaudeService.chat().
    if chat.is_empty() {
        match &context {
            Some(ChatContext::File { name, path }) => {
                if let Some(block) = file_block(path) {
                    content.push(block);
                }
                content.push(json!({ "type": "text", "text": format!("File: {name}") }));
            }
            Some(ChatContext::Window { app_name, title, url }) => {
                let mut text = format!("Context — App: {app_name}, Window: {title}");
                if let Some(url) = url {
                    text.push_str(&format!(", URL: {url}"));
                }
                content.push(json!({ "type": "text", "text": text }));
            }
            None => {}
        }
    }
    content.push(json!({ "type": "text", "text": query }));

    chat.push(json!({ "role": "user", "content": content }));

    // Seleccionar herramientas y prompt de acuerdo a la persona ("amiguito" vs default)
    let (system_text, tools) = if persona.as_deref() == Some("amiguito") {
        (
            "Eres el Amiguito Controlador. Tienes acceso a herramientas para buscar en internet y ejecutar PowerShell localmente en Windows. Tu propósito es automatizar acciones en la computadora abriendo aplicaciones, manejándolas con comandos, y buscando info web.",
            json!([
                {
                    "functionDeclarations": [
                        {
                            "name": "search_internet",
                            "description": "Busca en internet información actualizada.",
                            "parameters": {
                                "type": "OBJECT",
                                "properties": { "query": { "type": "STRING" } },
                                "required": ["query"]
                            }
                        },
                        {
                            "name": "control_pc",
                            "description": "Ejecuta un script de PowerShell en la computadora local. Úsalo para interactuar con el sistema, simular clics o teclado. MUY IMPORTANTE: Si vas a abrir una aplicación (como Spotify), DEBES usar 'Start-Process' y NUNCA llamar al .exe directamente, de lo contrario bloquearás todo el sistema.",
                            "parameters": {
                                "type": "OBJECT",
                                "properties": { "script": { "type": "STRING" } },
                                "required": ["script"]
                            }
                        },
                        {
                            "name": "take_screenshot",
                            "description": "Toma una captura de la pantalla principal y te la envía como una imagen para que puedas ver lo que hay en la pantalla y decidir dónde hacer clic o qué comandos mandar.",
                            "parameters": {
                                "type": "OBJECT",
                                "properties": {}
                            }
                        }
                    ]
                }
            ])
        )
    } else {
        (
            "Eres Cody, mi asistente personal para desarrollo y VS Code. Responde de forma directa, ejecutiva y sin rodeos.",
            json!([
                {
                    "functionDeclarations": [
                        {
                            "name": "control_pc",
                            "description": "Ejecuta un script de PowerShell. Úsalo para interactuar con el entorno de desarrollo y archivos.",
                            "parameters": {
                                "type": "OBJECT",
                                "properties": { "script": { "type": "STRING" } },
                                "required": ["script"]
                            }
                        }
                    ]
                },
                { "codeExecution": {} }
            ])
        )
    };

    let mut body = json!({
        "contents": gemini_contents(&chat.snapshot()),
        "tools": tools,
        "system_instruction": {
            "parts": [
                { "text": system_text }
            ]
        },
        "toolConfig": {
            "includeServerSideToolInvocations": true
        },
        "generationConfig": { "maxOutputTokens": MAX_TOKENS },
    });

    loop {
        let response = match call(&key, &body).await {
            Ok(v) => v,
            Err(err) => {
                chat.pop(); // keep the history consistent with what the model saw
                return Err(err);
            }
        };

        // Si la respuesta incluye un functionCall, ejecutamos la función
        if let Some(candidates) = response.get("candidates").and_then(Value::as_array) {
            if let Some(parts) = candidates.first().and_then(|c| c.get("content")).and_then(|c| c.get("parts")).and_then(Value::as_array) {
                if let Some(call) = parts.iter().find_map(|p| p.get("functionCall")) {
                    let name = call.get("name").and_then(Value::as_str).unwrap_or("");
                    let mut extra_parts = vec![];
                    
                    let result = if name == "search_internet" {
                        let q = call.get("args").and_then(|a| a.get("query")).and_then(Value::as_str).unwrap_or("");
                        search_duckduckgo(q).await
                    } else if name == "control_pc" {
                        let script = call.get("args").and_then(|a| a.get("script")).and_then(Value::as_str).unwrap_or("");
                        execute_powershell(script).await
                    } else if name == "take_screenshot" {
                        let script = r#"
Add-Type -AssemblyName System.Windows.Forms,System.Drawing;
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds;
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height;
$graphics = [System.Drawing.Graphics]::FromImage($bmp);
$graphics.CopyFromScreen($bounds.Left, $bounds.Top, 0, 0, $bmp.Size);
$stream = New-Object System.IO.MemoryStream;
$bmp.Save($stream, [System.Drawing.Imaging.ImageFormat]::Jpeg);
$bytes = $stream.ToArray();
[Convert]::ToBase64String($bytes)
"#;
                        let b64 = execute_powershell(script).await.trim().to_string();
                        if !b64.starts_with("Error:") && !b64.contains("Falló") && b64.len() > 100 {
                            extra_parts.push(json!({
                                "inlineData": {
                                    "mimeType": "image/jpeg",
                                    "data": b64
                                }
                            }));
                            "Captura de pantalla enviada.".to_string()
                        } else {
                            format!("Fallo al capturar: {}", b64)
                        }
                    } else {
                        "Función desconocida".to_string()
                    };

                    chat.push(json!({
                        "role": "assistant",
                        "content": parts
                    }));
                    
                    let mut user_parts = vec![
                        json!({
                            "functionResponse": {
                                "name": name,
                                "response": { "name": name, "content": result }
                            }
                        })
                    ];
                    user_parts.extend(extra_parts);
                    
                    chat.push(json!({
                        "role": "user",
                        "content": user_parts
                    }));

                    body["contents"] = Value::Array(gemini_contents(&chat.snapshot()));
                    continue;
                }
            }
        }

        let Some(text) = gemini_text(&response) else {
            chat.pop();
            return Err("Unexpected API response.".into());
        };

        chat.push(json!({
            "role": "assistant",
            "content": [{ "type": "text", "text": text }]
        }));

        return Ok(ChatReply { text });
    }
}

pub async fn list_models() -> Result<Vec<GeminiModel>, String> {
    let key = secrets::get("anthropic-api-key")
        .ok_or_else(|| "API key missing. Open settings.".to_string())?;
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .map_err(|e| e.to_string())?;
    let mut page_token: Option<String> = None;
    let mut models = Vec::new();

    loop {
        let mut endpoint = reqwest::Url::parse(MODELS_ENDPOINT).map_err(|e| e.to_string())?;
        endpoint.query_pairs_mut().append_pair("key", &key);
        if let Some(token) = &page_token {
            endpoint.query_pairs_mut().append_pair("pageToken", token);
        }
        let response = client
            .get(endpoint)
            .send()
            .await
            .map_err(|e| format!("Network error: {e}"))?;
        let status = response.status();
        let text = response.text().await.map_err(|e| e.to_string())?;
        let value: Value = serde_json::from_str(&text).map_err(|e| format!("Bad model list: {e}"))?;
        if !status.is_success() {
            return Err(format!("Gemini API {status}: {}", api_error(&value, &text)));
        }

        if let Some(items) = value.get("models").and_then(Value::as_array) {
            for item in items {
                let supports_generate = item
                    .get("supportedGenerationMethods")
                    .and_then(Value::as_array)
                    .is_some_and(|methods| methods.iter().any(|m| m.as_str() == Some("generateContent")));
                if !supports_generate {
                    continue;
                }
                let id = item
                    .get("baseModelId")
                    .and_then(Value::as_str)
                    .or_else(|| item.get("name").and_then(Value::as_str).and_then(|n| n.strip_prefix("models/")));
                let Some(id) = id else { continue };
                if models.iter().any(|model: &GeminiModel| model.id == id) {
                    continue;
                }
                models.push(GeminiModel {
                    id: id.to_string(),
                    display_name: item
                        .get("displayName")
                        .and_then(Value::as_str)
                        .unwrap_or(id)
                        .to_string(),
                });
            }
        }

        page_token = value.get("nextPageToken").and_then(Value::as_str).map(str::to_string);
        if page_token.is_none() {
            break;
        }
    }
    models.sort_by(|a, b| a.display_name.cmp(&b.display_name));
    Ok(models)
}

async fn call(key: &str, body: &Value) -> Result<Value, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(90))
        .build()
        .map_err(|e| e.to_string())?;

    let mut endpoint = reqwest::Url::parse(ENDPOINT).map_err(|e| e.to_string())?;
    endpoint.query_pairs_mut().append_pair("key", key.trim());

    let response = client
        .post(endpoint)
        .header("content-type", "application/json")
        .json(body)
        .send()
        .await
        .map_err(|e| format!("Network error: {e}"))?;

    let status = response.status();
    let text = response.text().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        // Surface the API's own message, which is what makes a bad key obvious.
        let detail = serde_json::from_str::<Value>(&text)
            .ok()
            .map(|v| api_error(&v, &text))
            .unwrap_or_else(|| text.chars().take(200).collect());
        return Err(format!("Gemini API {status}: {detail}"));
    }
    serde_json::from_str(&text).map_err(|e| format!("Bad API response: {e}"))
}

fn api_error(value: &Value, raw: &str) -> String {
    value
        .get("error")
        .and_then(|error| error.get("message"))
        .and_then(Value::as_str)
        .map(str::to_string)
        .unwrap_or_else(|| raw.chars().take(200).collect())
}

/// Converts the internal Anthropic-shaped history to Gemini's contents format.
/// Assistant turns become Gemini's `model` role; user turns remain `user`.
fn gemini_contents(messages: &[Value]) -> Vec<Value> {
    let mut recent: Vec<Value> = messages
        .iter()
        .filter(|message| matches!(message.get("role").and_then(Value::as_str), Some("user" | "assistant")))
        .rev()
        .take(30) // Aumentado de 3 a 30 para mejor memoria a corto plazo
        .cloned()
        .collect();

    recent.reverse();

    let mut history: Vec<Value> = recent
        .into_iter()
        .filter_map(|message| {
            let role = match message.get("role").and_then(Value::as_str) {
                Some("assistant") => "model",
                Some("user") => "user",
                _ => return None,
            };
            let parts = message
                .get("content")
                .and_then(Value::as_array)
                .map(|blocks| blocks.iter().filter_map(gemini_part).collect::<Vec<_>>())
                .unwrap_or_default();
            (!parts.is_empty()).then(|| json!({ "role": role, "parts": parts }))
        })
        .collect();

    // Sanear el historial: Gemini exige que cualquier `functionResponse` esté
    // precedido inmediatamente por un `functionCall`. Si al truncar el array
    // (take 30) cortamos el functionCall original, la API dará error 400.
    while !history.is_empty() {
        let first = &history[0];
        let has_response = first.get("parts")
            .and_then(Value::as_array)
            .is_some_and(|parts| parts.iter().any(|p| p.get("functionResponse").is_some()));
            
        if has_response {
            history.remove(0); // Descartar respuestas huérfanas
        } else {
            break;
        }
    }

    history
}

fn gemini_part(block: &Value) -> Option<Value> {
    if block.get("functionCall").is_some()
        || block.get("functionResponse").is_some()
        || block.get("executableCode").is_some()
        || block.get("codeExecutionResult").is_some()
        || block.get("inlineData").is_some()
    {
        return Some(block.clone());
    }
    if let Some(text) = block.get("text").and_then(Value::as_str) {
        if !text.trim().is_empty() {
            return Some(json!({ "text": text }));
        }
    }
    None
}

fn gemini_text(response: &Value) -> Option<String> {
    let text = response
        .get("candidates")?
        .as_array()?
        .first()?
        .get("content")?
        .get("parts")?
        .as_array()?
        .iter()
        .filter_map(|part| part.get("text").and_then(Value::as_str))
        .collect::<Vec<_>>()
        .join("\n")
        .trim()
        .to_string();
    if text.is_empty() {
        return None;
    }

    let sources = response
        .get("candidates")
        .and_then(Value::as_array)
        .and_then(|candidates| candidates.first())
        .and_then(|candidate| candidate.get("groundingMetadata"))
        .and_then(|metadata| metadata.get("groundingChunks"))
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|chunk| chunk.get("web"))
        .filter_map(|web| {
            Some((
                web.get("title").and_then(Value::as_str)?,
                web.get("uri").and_then(Value::as_str)?,
            ))
        })
        .collect::<Vec<_>>();

    let mut answer = text;
    if !sources.is_empty() {
        answer.push_str("\n\nFuentes:\n");
        for (title, uri) in sources {
            answer.push_str(&format!("- {title}: {uri}\n"));
        }
    }
    Some(answer)
}

/// PDF → document block, image → image block, text/code → inline text.
/// Mirrors readFileAsBlock() in ClaudeService.swift.
fn file_block(path: &str) -> Option<Value> {
    let ext = std::path::Path::new(path)
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_lowercase();

    let media_type = match ext.as_str() {
        "pdf" => Some(("document", "application/pdf")),
        "jpg" | "jpeg" => Some(("image", "image/jpeg")),
        "png" => Some(("image", "image/png")),
        "gif" => Some(("image", "image/gif")),
        "webp" => Some(("image", "image/webp")),
        _ => None,
    };

    if let Some((block_type, media)) = media_type {
        let bytes = std::fs::read(path).ok()?;
        return Some(json!({
            "type": block_type,
            "source": { "type": "base64", "media_type": media, "data": base64(&bytes) },
        }));
    }

    let len = std::fs::metadata(path).ok()?.len();
    if len > MAX_INLINE_TEXT {
        return None;
    }
    let text = std::fs::read_to_string(path).ok()?;
    Some(json!({ "type": "text", "text": format!("File contents:\n{text}") }))
}

/// Small standalone base64 encoder — not worth another dependency.
/// Also used for Stripe's basic auth.
pub(crate) fn base64_for(bytes: &[u8]) -> String {
    base64(bytes)
}

fn base64(bytes: &[u8]) -> String {
    const TABLE: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::with_capacity(bytes.len().div_ceil(3) * 4);
    for chunk in bytes.chunks(3) {
        let b = [chunk[0], *chunk.get(1).unwrap_or(&0), *chunk.get(2).unwrap_or(&0)];
        let n = ((b[0] as u32) << 16) | ((b[1] as u32) << 8) | b[2] as u32;
        out.push(TABLE[(n >> 18) as usize & 63] as char);
        out.push(TABLE[(n >> 12) as usize & 63] as char);
        out.push(if chunk.len() > 1 { TABLE[(n >> 6) as usize & 63] as char } else { '=' });
        out.push(if chunk.len() > 2 { TABLE[n as usize & 63] as char } else { '=' });
    }
    out
}

#[cfg(test)]
mod tests {
    use super::{base64, gemini_contents, gemini_text};
    use serde_json::json;

    #[test]
    fn base64_matches_rfc4648_vectors() {
        assert_eq!(base64(b""), "");
        assert_eq!(base64(b"f"), "Zg==");
        assert_eq!(base64(b"fo"), "Zm8=");
        assert_eq!(base64(b"foo"), "Zm9v");
        assert_eq!(base64(b"foob"), "Zm9vYg==");
        assert_eq!(base64(b"fooba"), "Zm9vYmE=");
        assert_eq!(base64(b"foobar"), "Zm9vYmFy");
    }

    #[test]
    fn adapts_history_to_gemini_contents() {
        let history = vec![
            json!({ "role": "user", "content": [{ "type": "text", "text": "hello" }] }),
            json!({ "role": "assistant", "content": [{ "type": "text", "text": "hi" }] }),
        ];
        let expected = json!([
            { "role": "user", "parts": [{ "text": "hello" }] },
            { "role": "model", "parts": [{ "text": "hi" }] },
        ])
        .as_array()
        .cloned()
        .unwrap();
        assert_eq!(gemini_contents(&history), expected);
    }

    #[test]
    fn extracts_text_from_gemini_response() {
        let response = json!({
            "candidates": [{ "content": { "parts": [{ "text": "answer" }] } }]
        });
        assert_eq!(gemini_text(&response).as_deref(), Some("answer"));
    }
}

pub(crate) async fn search_duckduckgo(query: &str) -> String {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .unwrap_or_default();
    
    let url = format!("https://html.duckduckgo.com/html/?q={}", query.replace(' ', "+"));

    let Ok(response) = client
        .get(&url)
        .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        .send()
        .await else {
        return "Error: No se pudo conectar a la búsqueda.".into();
    };

    let Ok(html) = response.text().await else {
        return "Error: No se pudo leer la respuesta.".into();
    };

    let mut results = String::new();
    let mut count = 0;
    
    for part in html.split("class=\"result__snippet") {
        if count >= 3 { break; }
        if part.starts_with('\"') || part.starts_with(' ') {
            if let Some(start) = part.find('>') {
                if let Some(end) = part[start..].find("</a>") {
                    let snippet = &part[start + 1..start + end];
                    let clean = snippet.replace("<b>", "").replace("</b>", "").replace("&#39;", "'").replace("&quot;", "\"");
                    results.push_str(&format!("- {}\n", clean.trim()));
                    count += 1;
                }
            }
        }
    }

    if results.is_empty() {
        "No se encontraron resultados relevantes.".into()
    } else {
        results
    }
}

async fn execute_powershell(script: &str) -> String {
    use std::process::Command;
    
    let output = Command::new("powershell")
        .arg("-NoProfile")
        .arg("-NonInteractive")
        .arg("-Command")
        .arg(script)
        .output();
        
    match output {
        Ok(out) => {
            let stdout = String::from_utf8_lossy(&out.stdout).to_string();
            let stderr = String::from_utf8_lossy(&out.stderr).to_string();
            if !stderr.trim().is_empty() {
                format!("Error:\n{}\nSalida:\n{}", stderr, stdout)
            } else if stdout.trim().is_empty() {
                "Ejecutado con éxito (sin salida).".to_string()
            } else {
                stdout
            }
        }
        Err(e) => format!("Falló al ejecutar PowerShell: {}", e),
    }
}
