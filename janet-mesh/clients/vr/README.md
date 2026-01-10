# VR Client for Janet Mesh Network

Virtual Reality client application for interacting with Janet in a 3D environment.

## Architecture

```
VR Client (Unity/Unreal) <--WebRTC--> Janet Mesh Server <--> Janet-seed
```

## Features

- Real-time 3D Janet model with animations
- Voice input/output via WebRTC
- Lip-sync animation driven by TTS audio
- Tone-aware gestures and idle animations
- Eye tracking and attention system
- VR Theater mode with Plex integration (stretch goal)

## Requirements

### Unity Version
- Unity 2021.3 LTS or newer
- Meta XR SDK or OpenXR

### Unreal Version
- Unreal Engine 5.0 or newer
- Meta XR SDK or OpenXR

### Dependencies
- WebRTC libraries (native or plugin)
- GLTF importer (Unity: GLTFast, Unreal: GLTF)
- Audio streaming libraries

## Project Structure

```
vr/
├── unity/                    # Unity project
│   ├── Assets/
│   │   ├── Scripts/
│   │   │   ├── JanetModelController.cs
│   │   │   ├── VRAudioBridge.cs
│   │   │   └── PlexTheaterController.cs
│   │   ├── Models/
│   │   │   └── Janet.gltf    # Janet 3D model
│   │   └── Materials/
│   └── ProjectSettings/
├── unreal/                   # Unreal project
│   ├── Content/
│   │   ├── Blueprints/
│   │   │   ├── JanetModelController
│   │   │   └── VRAudioBridge
│   │   └── Models/
│   │       └── Janet.gltf
│   └── Config/
└── README.md
```

## Setup Instructions

### Unity Setup

1. Create new Unity project (3D template)
2. Install Meta XR SDK or OpenXR via Package Manager
3. Install GLTFast from Asset Store or GitHub
4. Import Janet.gltf model
5. Add WebRTC plugin (e.g., Unity WebRTC package)
6. Configure WebSocket connection to Janet Mesh server

### Unreal Setup

1. Create new Unreal project (VR template)
2. Install Meta XR SDK or OpenXR plugin
3. Import Janet.gltf model using GLTF importer
4. Set up WebRTC C++ plugins
5. Configure WebSocket connection to Janet Mesh server

## Integration with Janet Mesh Server

The VR client communicates with Janet Mesh server via WebSocket:

### Connection Flow

1. VR client connects to WebSocket server (`ws://SERVER_IP:8765/ws`)
2. Send `vr_connect` message with `session_id`
3. Receive `vr_offer` with WebRTC SDP offer
4. Generate WebRTC answer and send via `vr_audio` message
5. Stream audio bi-directionally via WebRTC data channel

### Message Types

**vr_connect**: Initiate VR connection
```json
{
  "type": "vr_connect",
  "session_id": "unique-session-id"
}
```

**vr_audio**: Send audio input or WebRTC answer
```json
{
  "type": "vr_audio",
  "session_id": "unique-session-id",
  "audio": "base64-encoded-audio-data",
  "sdp": "optional-webrtc-answer-sdp",
  "sdp_type": "answer"
}
```

**vr_response**: Receive response from Janet
```json
{
  "type": "vr_response",
  "session_id": "unique-session-id",
  "text": "Janet's response text",
  "status": "processed"
}
```

## 3D Model Animation

### Viseme Blendshapes

The Janet model should have viseme blendshapes for lip-sync:
- A (ah), E (eh), I (ih), O (oh), U (uh)
- M (mm), F (ff), Th (th), P (p), etc.

### Animation System

- **Idle animations**: Tone-aware based on conversation context
- **Gesture system**: Reflects Janet's emotional state
- **Lip-sync**: Driven by TTS audio stream using viseme detection
- **Eye tracking**: Model looks at Operator (head tracking)

## Implementation Status

- [x] VR Audio Bridge (server-side)
- [x] WebSocket integration
- [ ] Unity project structure
- [ ] Unreal project structure
- [ ] 3D model loading
- [ ] Viseme blendshape system
- [ ] Animation controller
- [ ] WebRTC audio streaming
- [ ] VR Theater mode with Plex

## Future Enhancements

- Hand tracking for gesture-based interaction
- Spatial audio for immersive experience
- Haptic feedback integration
- Multi-user VR sessions
- Virtual environment customization
