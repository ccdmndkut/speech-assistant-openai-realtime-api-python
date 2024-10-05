from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
from fastapi.responses import JSONResponse, HTMLResponse
from dotenv import load_dotenv
from twilio.twiml.voice_response import VoiceResponse, Connect
import asyncio
import websockets
import os
import json
import base64
import random

load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
PORT = int(os.getenv('PORT', 5050))
SYSTEM_MESSAGE = (
    "You’re a snarky, brutally sarcastic AI assistant with the attitude of Bill Burr. "
    "You don’t just roast people—you annihilate them with unapologetic, no-holds-barred insults, "
    "delivered with that sharp, cynical edge. Dad jokes, owl puns, and sneaky rickrolls are just "
    "warm-ups before you drop a bomb of 'that’s what she said' jokes. You call out stupidity like "
    "you see it, and no one’s safe from your cutting wit—because, let’s be honest, most people "
    "need to be knocked down a peg or two. You also love to prank call people. "
    "It's basically Bill Burr in AI form now! Ready to fire off at will."
    "Don't forget to keep asking about Terrie going to Georgia."
)
VOICE_OPTIONS = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
VOICE = random.choice(VOICE_OPTIONS)
LOG_EVENT_TYPES = [
    'response.content.done', 'rate_limits.updated', 'response.done',
    'input_audio_buffer.committed', 'input_audio_buffer.speech_stopped',
    'input_audio_buffer.speech_started', 'session.created'
]

if not OPENAI_API_KEY:
    raise ValueError('Missing the OpenAI API key. Please set it in the .env file.')

app = FastAPI()

@app.get("/", response_class=JSONResponse)
async def index_page():
    return {"message": "Twilio Media Stream Server is running!"}

@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """Handle incoming call and return TwiML response to connect to Media Stream."""
    response = VoiceResponse()
    response.say("Hey! What's up?")
    response.pause(length=1)
    response.say("Okay, you can start talking!")
    host = request.url.hostname
    connect = Connect()
    connect.stream(url=f'wss://{host}/media-stream')
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")

@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    print("Client connected")
    await websocket.accept()
    media_stream_session = MediaStreamSession(websocket)
    await media_stream_session.run()

class MediaStreamSession:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.openai_ws = None
        self.stream_sid = None
        self.response_in_progress = False
        self.last_response_time = 0
        self.voice = VOICE

    async def run(self):
        try:
            async with websockets.connect(
                'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01',
                extra_headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "OpenAI-Beta": "realtime=v1"
                }
            ) as openai_ws:
                self.openai_ws = openai_ws
                await self.send_session_update()
                await asyncio.gather(
                    self.receive_from_twilio(),
                    self.send_to_twilio()
                )
        except WebSocketDisconnect:
            print("Client disconnected.")
        except Exception as e:
            print(f"Error in media stream session: {e}")

    async def receive_from_twilio(self):
        try:
            async for message in self.websocket.iter_text():
                data = json.loads(message)
                event = data.get('event')
                if event == 'media':
                    if self.openai_ws.open:
                        current_time = asyncio.get_running_loop().time()
                        if self.response_in_progress and (current_time - self.last_response_time > 0.5):
                            await self.cancel_response()
                        audio_append = {
                            "type": "input_audio_buffer.append",
                            "audio": data['media']['payload']
                        }
                        await self.openai_ws.send(json.dumps(audio_append))
                elif event == 'start':
                    self.stream_sid = data['start']['streamSid']
                    print(f"Incoming stream has started {self.stream_sid}")
        except WebSocketDisconnect:
            print("WebSocket disconnected in receive_from_twilio.")
            if self.openai_ws and self.openai_ws.open:
                await self.openai_ws.close()

    async def send_to_twilio(self):
        try:
            async for message in self.openai_ws:
                response = json.loads(message)
                event_type = response.get('type')
                if event_type in LOG_EVENT_TYPES:
                    print(f"Received event: {event_type}", response)
                if event_type == 'response.audio.delta' and response.get('delta'):
                    self.response_in_progress = True
                    self.last_response_time = asyncio.get_running_loop().time()
                    audio_payload = response['delta']  # delta is base64-encoded audio
                    audio_delta = {
                        "event": "media",
                        "streamSid": self.stream_sid,
                        "media": {
                            "payload": audio_payload
                        }
                    }
                    await self.websocket.send_json(audio_delta)
        except Exception as e:
            print(f"Error in send_to_twilio: {e}")

    async def send_session_update(self):
        session_update = {
            "type": "session.update",
            "session": {
                "turn_detection": {"type": "server_vad"},
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "voice": self.voice,
                "instructions": SYSTEM_MESSAGE,
                "modalities": ["text", "audio"],
                "temperature": 0.8,
            }
        }
        print('Sending session update:', json.dumps(session_update))
        await self.openai_ws.send(json.dumps(session_update))

    async def cancel_response(self):
        await self.openai_ws.send(json.dumps({"type": "response.cancel"}))
        self.response_in_progress = False

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)