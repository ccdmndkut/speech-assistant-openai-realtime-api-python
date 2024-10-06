# Realtime API Documentation

## Introduction

The Realtime API enables you to build low-latency, multi-modal conversational experiences. It currently supports **text and audio** as both **input** and **output**, as well as [function calling](/docs/guides/function-calling).

### Benefits

1. **Native speech-to-speech:** No text intermediary means low latency, nuanced output.
2. **Natural, steerable voices:** The models have a natural inflection and can laugh, whisper, and adhere to tone direction.
3. **Simultaneous multimodal output:** Text is useful for moderation, faster-than-realtime audio ensures stable playback.

## Quickstart

The Realtime API is a WebSocket interface designed to run on the server. A console demo application is available to help you get started quickly. **Note:** The frontend patterns in this app are not recommended for production.

[Get started with the Realtime console](https://github.com/openai/openai-realtime-console)

## Overview

The Realtime API is a **stateful**, **event-based** API that communicates over a WebSocket. The WebSocket connection requires:

- **URL:** `wss://api.openai.com/v1/realtime`
- **Query Parameters:** `?model=gpt-4o-realtime-preview-2024-10-01`
- **Headers:**
  - `Authorization: Bearer YOUR_API_KEY`
  - `OpenAI-Beta: realtime=v1`

### Example

Below is a simple example using the [`ws` library in Node.js](https://github.com/websockets/ws):

```javascript
import WebSocket from "ws";

const url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01";
const ws = new WebSocket(url, {
    headers: {
        "Authorization": "Bearer " + process.env.OPENAI_API_KEY,
        "OpenAI-Beta": "realtime=v1",
    },
});

ws.on("open", function open() {
    console.log("Connected to server.");
    ws.send(JSON.stringify({
        type: "response.create",
        response: {
            modalities: ["text"],
            instructions: "Please assist the user.",
        }
    }));
});

ws.on("message", function incoming(message) {
    console.log(JSON.parse(message.toString()));
});
```

## Concepts

The Realtime API maintains the state of interactions throughout the lifetime of a session.

### Session

A session refers to a single WebSocket connection between a client and the server. It can be updated at any time (via `session.update`) or on a per-response level (via `response.create`).

### Conversation

A realtime Conversation consists of a list of Items. By default, there is only one Conversation, created at the beginning of the Session.

### Items

A realtime Item can be of three types: `message`, `function_call`, or `function_call_output`.

## Input Audio Buffer

The server maintains an Input Audio Buffer containing client-provided audio that has not yet been committed to the conversation state.

## Responses

The server's response timing depends on the `turn_detection` configuration.

## Function Calls

The client can set default functions for the server in a `session.update` message, or set per-response functions in the `response.create` message.

## Audio Formats

The realtime API supports raw 16 bit PCM audio at 24kHz, 1 channel, little-endian, and G.711 at 8kHz (both u-law and a-law).

## Instructions

You can control the content of the server's response by setting `instructions` on the session or per-response.

## Sending and Receiving Events

To send events to the API, you must send a JSON string containing your event payload data. To receive events, listen for the WebSocket `message` event, and parse the result as JSON.

## Handling Errors

All errors are passed from the server to the client with an `error` event.

## Continuing Conversations

The Realtime API is ephemeral — sessions and conversations are not stored on the server after a connection ends.

## Handling Long Conversations

If a conversation exceeds the model’s input context limit, the Realtime API automatically truncates the conversation based on a heuristic-based algorithm.

## Events

There are [9 client events](/docs/api-reference/realtime-client-events) you can send and [28 server events](/docs/api-reference/realtime-server-events) you can listen to.

## Pausing and Resuming Sessions

The Realtime API allows you to pause and resume sessions to manage the flow of interactions effectively. This can be useful in scenarios where you need to temporarily halt the conversation without closing the WebSocket connection.

### How to Pause a Session

To pause a session, you can send a `session.pause` event. This event will temporarily halt the processing of incoming messages and responses.

```json
{
    "type": "session.pause"
}
```

### How to Resume a Session

To resume a paused session, send a `session.resume` event. This will restart the processing of messages and responses.

```json
{
    "type": "session.resume"
}
```

### Use Cases

- **User Interruption:** Pause the session when the user needs to take a break or when an interruption occurs.
- **Resource Management:** Temporarily halt the session to manage server resources more effectively.
- **Controlled Interaction:** Use pausing to control the pace of the conversation, ensuring that responses are only processed when needed.

### Considerations

- **State Maintenance:** While a session is paused, the state of the conversation is maintained, and no new messages are processed until the session is resumed.
- **Timeouts:** Be aware of any server-side timeouts that may affect paused sessions. Ensure that sessions are resumed before any timeout limits are reached to avoid disconnection.

For more detailed information on session management, refer to the [API reference page](/docs/api-reference/realtime-client-events).