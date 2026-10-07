use base64::{engine::general_purpose::STANDARD, Engine as _};
use futures_util::{SinkExt, StreamExt};
use tokio::net::UdpSocket;
use rodio::{buffer::SamplesBuffer, OutputStream, Sink};
use serde_json::{json, Value};
use std::sync::{Arc, atomic::{AtomicBool, AtomicU64, Ordering}};
use tokio_tungstenite::{connect_async, tungstenite::protocol::Message};
use tauri::Emitter;


const LIVE_ENDPOINT: &str =
    "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent";
const LIVE_MODEL: &str = "models/gemini-3.8-live";

pub async fn start_live_session(app: tauri::AppHandle) -> Result<(), String> {
    let env_bytes = std::fs::read(r#"C:\Users\Joako\OneDrive\Escritorio\Coucou\Caf\.env"#)
        .map_err(|_| "Failed to read .env file".to_string())?;
    
    // Handle potential UTF-16 by stripping null bytes, then convert to string
    let env_clean: Vec<u8> = env_bytes.into_iter().filter(|&b| b != 0).collect();
    let env_content = String::from_utf8_lossy(&env_clean);
    
    let mut api_key = String::new();
    for line in env_content.lines() {
        if line.contains("GEMINI_API_KEY") {
            if let Some(idx) = line.find('=') {
                api_key = line[idx+1..].trim().trim_matches('"').trim_matches('\'').to_string();
                break;
            }
        }
    }
    
    if api_key.is_empty() {
        return Err("GEMINI_API_KEY not found in .env".to_string());
    }

    let url = format!("{}?key={}", LIVE_ENDPOINT, api_key);

    println!("Connecting to Gemini Live API...");
    let (ws_stream, _) = connect_async(&url).await.map_err(|e| format!("WS Error: {}", e))?;
    let (mut ws_write, mut ws_read) = ws_stream.split();

    // 1. Send Setup message with VAD configuration
    let setup_msg = json!({
        "setup": {
            "model": LIVE_MODEL,
            "systemInstruction": {
                "parts": [
                    { "text": "Sos Coucou, el asistente de Joako. Respondé rápido, natural y en argentino. Nunca digas 'Hola'. Andá al grano. Esto es una llamada de voz en tiempo real. Mantené la conversación activa, hacé preguntas de seguimiento cuando tenga sentido." }
                ]
            },
            "tools": [
                {
                    "functionDeclarations": [
                        {
                            "name": "control_pc",
                            "description": "Ejecuta un script de PowerShell en la PC local. Úsalo para abrir aplicaciones, controlar volumen, etc. IMPORTANTE: Para abrir la app nativa de Spotify, NUNCA intentes abrir el protocolo ni Start-Process spotify, DEBES usar EXACTAMENTE: `explorer.exe shell:AppsFolder\\SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify`. Antes de usar esta herramienta, debes avisarle al usuario lo que vas a hacer y decirle que espere.",
                            "parameters": {
                                "type": "OBJECT",
                                "properties": {
                                    "script": {
                                        "type": "STRING",
                                        "description": "El script de PowerShell a ejecutar."
                                    }
                                },
                                "required": ["script"]
                            }
                        },
                        {
                            "name": "search_internet",
                            "description": "Busca información en Internet. Úsalo SIEMPRE que el usuario te pregunte algo sobre el clima, noticias actuales, datos en tiempo real o cualquier información que no sepas. Recibirás un resumen con los resultados para responderle al usuario.",
                            "parameters": {
                                "type": "OBJECT",
                                "properties": {
                                    "query": {
                                        "type": "STRING",
                                        "description": "La consulta de búsqueda (ej: 'clima en buenos aires')."
                                    }
                                },
                                "required": ["query"]
                            }
                        },
                        {
                            "name": "cerrar_llamada",
                            "description": "Cierra la llamada y apaga el micrófono. Úsalo si el usuario dice 'chau' o pide explícitamente terminar la llamada."
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": "Orus"
                        }
                    }
                }
            }
        }
    });

    ws_write
        .send(Message::Text(setup_msg.to_string().into()))
        .await
        .map_err(|e| format!("Send Setup Error: {}", e))?;

    // Wait for setup completion from server
    match ws_read.next().await {
        Some(Ok(msg)) => {
            println!("Gemini Setup Response: {:?}", msg);
            if let Message::Text(text) = msg {
                println!("Setup Complete: {}", text);
            }
        }
        Some(Err(e)) => return Err(format!("Gemini Setup Error: {:?}", e)),
        None => return Err("Gemini Setup: Connection closed immediately".to_string()),
    }

    println!("Gemini Live session ready. Waiting for voice input...");

    let (tx_play, rx_play) = std::sync::mpsc::channel::<Vec<i16>>();

    let play_until_ms = Arc::new(AtomicU64::new(0));
    let is_interrupted = Arc::new(AtomicBool::new(false));
    let server_turn_active = Arc::new(AtomicBool::new(false));

    let _play_until_mic = play_until_ms.clone();
    let is_interrupted_mic = is_interrupted.clone();
    let server_turn_active_mic = server_turn_active.clone();

    let play_until_ms_clone = Arc::clone(&play_until_ms);
    std::thread::spawn(move || {
        let (_stream, stream_handle) = match OutputStream::try_default() {
            Ok(res) => res,
            Err(e) => {
                eprintln!("Failed to open output stream: {}", e);
                return;
            }
        };
        let sink = match Sink::try_new(&stream_handle) {
            Ok(s) => s,
            Err(e) => {
                eprintln!("Failed to create sink: {}", e);
                return;
            }
        };
        let _udp_out = std::net::UdpSocket::bind("127.0.0.1:0").expect("Failed to bind UDP out");

        loop {
            if is_interrupted.load(Ordering::Relaxed) {
                sink.clear();
                play_until_ms_clone.store(0, Ordering::Relaxed);
                is_interrupted.store(false, Ordering::Relaxed);
            }

            let now = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_millis() as u64;
            if !sink.empty() {
                // If sink is still playing, push the silence window 400ms into the future.
                play_until_ms_clone.store(now + 400, Ordering::Relaxed);
            }

            // Block up to 20ms waiting for the next audio chunk (avoids thread sleeping arbitrarily)
            if let Ok(first) = rx_play.recv_timeout(std::time::Duration::from_millis(20)) {
                let mut combined_data = first;
                // Drain any other chunks that arrived at the same time
                while let Ok(mut more) = rx_play.try_recv() {
                    combined_data.append(&mut more);
                }
                
                let source = SamplesBuffer::new(1, 24000, combined_data);
                sink.append(source);
                
                // Push the silence window
                let now_after = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_millis() as u64;
                play_until_ms_clone.store(now_after + 400, Ordering::Relaxed);
            } else {
                // recv_timeout hit (no new audio). Check if sink is STILL playing!
                if !sink.empty() {
                    let now_after = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_millis() as u64;
                    play_until_ms_clone.store(now_after + 400, Ordering::Relaxed);
                }
            }
        }
    });

    println!("Microphone listening via UDP & sending to Gemini...");
    let udp_socket = UdpSocket::bind("127.0.0.1:4000").await.map_err(|e| format!("UDP bind error: {}", e))?;
    let mut udp_buf = vec![0u8; 8000];
    let mut packet_count: u64 = 0;
    let mut last_send_time = std::time::Instant::now();

    // 3. Main Event Loop
    let mut sent_audio_in_turn = false;
    let mut was_silenced = false; // Track state to tell Python to pause/resume Vosk

    loop {
        tokio::select! {
            // Keepalive: send empty audio chunk every 15s to prevent silent disconnection
            _ = tokio::time::sleep(std::time::Duration::from_secs(15)) => {
                if last_send_time.elapsed().as_secs() > 14 {
                    if ws_write.send(Message::Ping(vec![].into())).await.is_err() {
                        println!("WebSocket closed during keepalive.");
                        break;
                    }
                    last_send_time = std::time::Instant::now();
                    println!("Sent keepalive to Gemini.");
                }
            }

            // Audio input from Python via UDP
            recv_res = udp_socket.recv_from(&mut udp_buf) => {
                if let Ok((size, _)) = recv_res {
                    if &udp_buf[..size] == b"TURN_COMPLETE" {
                        if !sent_audio_in_turn {
                            println!("Ignoring false TURN_COMPLETE (speaker echo / no mic data).");
                            continue;
                        }
                        println!("Vosk VAD detected silence. Sending turnComplete...");
                        let _ = app.emit("voice-status", "Gemini está pensando...");
                        let turn_complete_req = json!({
                            "clientContent": {
                                "turnComplete": true
                            }
                        });
                        let _ = ws_write.send(Message::Text(turn_complete_req.to_string().into())).await;
                        sent_audio_in_turn = false;
                        continue;
                    }

                    // Calculate RMS to detect voice activity (for logging only)
                    let mut sum_sq: u64 = 0;
                    let samples = size / 2;
                    for i in 0..samples {
                        let low = udp_buf[i * 2] as u16;
                        let high = udp_buf[i * 2 + 1] as u16;
                        let sample = (low | (high << 8)) as i16;
                        sum_sq += (sample as i64 * sample as i64) as u64;
                    }
                    let rms = ((sum_sq as f64 / samples as f64).sqrt()) as i32;
                    packet_count += 1;

                    let now_ms = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_millis() as u64;
                    let mut is_silenced = false;
                    let current_until = play_until_ms.load(Ordering::Relaxed);
                    if server_turn_active_mic.load(Ordering::Relaxed) || now_ms < current_until + 300 {
                        // Speaker is playing audio or Gemini is actively generating. Send silence to prevent echo loop!
                        is_silenced = true;
                    }

                    if is_silenced != was_silenced {
                        was_silenced = is_silenced;
                        if let Ok(mut lock) = crate::CAF_STDIN.lock() {
                            if let Some(stdin) = lock.as_mut() {
                                let cmd: &[u8] = if is_silenced { b"SILENCE_VOSK_ON\n" } else { b"SILENCE_VOSK_OFF\n" };
                                let _ = std::io::Write::write_all(stdin, cmd);
                                let _ = std::io::Write::flush(stdin);
                            }
                        }
                        
                        // Synchronize UI perfectly with mic/speaker state
                        if !is_silenced {
                            let _ = app.emit("voice-status", "Esperando tu voz...");
                        } else {
                            let _ = app.emit("voice-status", "Gemini está hablando...");
                        }
                    }

                    let base64_audio = if is_silenced {
                        let zeros = vec![0u8; size];
                        STANDARD.encode(&zeros)
                    } else {
                        STANDARD.encode(&udp_buf[..size])
                    };

                    let msg = json!({
                        "realtimeInput": {
                            "mediaChunks": [{
                                "mimeType": "audio/pcm;rate=16000",
                                "data": base64_audio
                            }]
                        }
                    });
                    
                    if ws_write.send(Message::Text(msg.to_string().into())).await.is_err() {
                        println!("WebSocket closed by server.");
                        break;
                    }
                    if !is_silenced {
                        sent_audio_in_turn = true;
                    }
                    last_send_time = std::time::Instant::now();
                    
                    if packet_count % 40 == 0 { // log every ~1s to avoid spam
                        if rms > 150 {
                            println!("🎤 Voice sending... (RMS: {})", rms);
                            let _ = app.emit("voice-status", "Te estoy escuchando...");
                        }
                    }
                }
            }
            
            // Messages from Gemini
            ws_msg = ws_read.next() => {
                match ws_msg {
                    Some(Ok(msg)) => {
                        let text_opt = match msg {
                            Message::Text(t) => Some(t.to_string()),
                            Message::Binary(b) => String::from_utf8(b.to_vec()).ok(),
                            Message::Close(c) => {
                                println!("WebSocket closed gracefully: {:?}", c);
                                break;
                            }
                            _ => None,
                        };

                        if let Some(text) = text_opt {
                            if text.len() > 1000 {
                                println!("Gemini says: [Audio payload received, {} bytes]", text.len());
                            } else {
                                println!("Gemini says: {}", text);
                            }
                            if let Ok(val) = serde_json::from_str::<Value>(&text) {
                                if let Some(server_content) = val.get("serverContent") {
                                    if server_content.get("interrupted").and_then(Value::as_bool) == Some(true) {
                                        println!("Gemini was interrupted by the user!");
                                        is_interrupted_mic.store(true, Ordering::Relaxed);
                                    }

                                    if let Some(turn) = server_content.get("modelTurn") {
                                        sent_audio_in_turn = false;
                                        if let Some(parts) = turn.get("parts").and_then(Value::as_array) {
                                            for part in parts {
                                                // Handle Text (Emit to Chat UI)
                                                if let Some(text_val) = part.get("text").and_then(Value::as_str) {
                                                    let _ = app.emit("gemini-reply", text_val);
                                                }
                                                // Handle Audio
                                                if let Some(inline) = part.get("inlineData") {
                                                    if let Some(b64) = inline.get("data").and_then(Value::as_str) {
                                                        if let Ok(decoded) = STANDARD.decode(b64) {
                                                            let _ = app.emit("voice-status", "Gemini está hablando...");
                                                            println!("Queuing {} bytes of audio for playback", decoded.len());
                                                            let mut i16_data = Vec::with_capacity(decoded.len() / 2);
                                                            for chunk in decoded.chunks_exact(2) {
                                                                i16_data.push(i16::from_le_bytes([chunk[0], chunk[1]]));
                                                            }
                                                            let _ = tx_play.send(i16_data);
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    if server_content.get("modelTurn").is_some() {
                                        server_turn_active.store(true, Ordering::Relaxed);
                                    }
                                    if let Some(turn_complete) = server_content.get("turnComplete").and_then(Value::as_bool) {
                                        if turn_complete {
                                            server_turn_active.store(false, Ordering::Relaxed);
                                        }
                                    }
                                }
                                
                                // Parse Tool Calls at ROOT level!
                                if let Some(tool_call) = val.get("toolCall") {
                                    if let Some(function_calls) = tool_call.get("functionCalls").and_then(Value::as_array) {
                                        for call in function_calls {
                                            if let Some(name) = call.get("name").and_then(Value::as_str) {
                                                let call_id = call.get("id").and_then(Value::as_str).unwrap_or("");
                                                
                                                if name == "control_pc" {
                                                    let script = call.get("args").and_then(|a| a.get("script")).and_then(Value::as_str).unwrap_or("");
                                                    println!("Executing Tool: control_pc -> {}", script);
                                                    let _ = app.emit("voice-status", "Ejecutando acción en la PC...");
                                                    let _ = std::process::Command::new("powershell")
                                                        .args(["-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script])
                                                        .spawn();
                                                    
                                                    let tool_response = json!({
                                                        "toolResponse": {
                                                            "functionResponses": [{
                                                                "name": "control_pc",
                                                                "id": call_id,
                                                                "response": { "result": "Acción ejecutada correctamente en la PC. (Instrucción: confírmale al usuario brevemente que ya lo hiciste)." }
                                                            }]
                                                        }
                                                    });
                                                    let _ = ws_write.send(Message::Text(tool_response.to_string().into())).await;
                                                    
                                                    // Force Gemini to respond immediately after the tool executes
                                                    let turn_complete_req = json!({
                                                        "clientContent": {
                                                            "turnComplete": true
                                                        }
                                                    });
                                                    let _ = ws_write.send(Message::Text(turn_complete_req.to_string().into())).await;
                                                } else if name == "search_internet" {
                                                    let query = call.get("args").and_then(|a| a.get("query")).and_then(Value::as_str).unwrap_or("");
                                                    println!("Executing Tool: search_internet -> {}", query);
                                                    let _ = app.emit("voice-status", "Buscando en Internet...");
                                                    let results = crate::claude::search_duckduckgo(query).await;
                                                    let tool_response = json!({
                                                        "toolResponse": {
                                                            "functionResponses": [{
                                                                "name": "search_internet",
                                                                "id": call_id,
                                                                "response": { "result": results }
                                                            }]
                                                        }
                                                    });
                                                    let _ = ws_write.send(Message::Text(tool_response.to_string().into())).await;
                                                    
                                                    // Force Gemini to respond immediately after the tool executes
                                                    let turn_complete_req = json!({
                                                        "clientContent": {
                                                            "turnComplete": true
                                                        }
                                                    });
                                                    let _ = ws_write.send(Message::Text(turn_complete_req.to_string().into())).await;
                                                } else if name == "cerrar_llamada" {
                                                    println!("Executing Tool: cerrar_llamada");
                                                    let _ = app.emit("voice-status", "Llamada finalizada");
                                                    let tool_response = json!({
                                                        "toolResponse": {
                                                            "functionResponses": [{
                                                                "name": "cerrar_llamada",
                                                                "id": call_id,
                                                                "response": { "result": "OK" }
                                                            }]
                                                        }
                                                    });
                                                    let _ = ws_write.send(Message::Text(tool_response.to_string().into())).await;
                                                    let _ = ws_write.send(Message::Close(None)).await;
                                                    return Ok(());
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    Some(Err(e)) => {
                        eprintln!("WebSocket Error: {}", e);
                        break;
                    }
                    None => {
                        println!("WebSocket connection closed unexpectedly.");
                        break;
                    }
                }
            }
        }
    }

    Ok(())
}
