
# ⚡ alive

A lightweight, asynchronous static HTTP server for development featuring smart live-reloading without full page refreshes.

Powered by Python asyncio and watchfiles, it utilizes SSE (Server-Sent Events) and Idiomorph to morph the DOM tree instantly when files change

## 🔥 Features

* ⚡ Flicker-Free Reloads: Updates code instantly without annoying screen flashes.
* 💾 State Preservation: Maintains inputs, scroll positions, and form data across updates.
* 🎨 Smooth Assets Morphing: Hot-swaps HTML, CSS, and all popular image formats seamlessly.
* 🌐 Fully Asynchronous: Engineered entirely on asyncio for maximum concurrent performance.

## 🛠️ Tech Stack

* Python 3.10+ (asyncio ecosystem)
* watchfiles — Fast, Rust-backed cross-platform file watching
* SSE (Server-Sent Events) — Native unidirectional browser streaming
* Idiomorph — Advanced Javascript library for morphing elements

## 💡 Use Cases

**alive** was developed for Documentation Dev Mode (Sphinx, MkDocs), but you can use it for any python tooling that needs to display changing html documents.

> [!warning]
> **alive** is not suitable if if you need to serve something more than static websites, such as complex javascript scripts or Single Page Applications

## 🚀 Quick Start

### Installation

```sh
pip install alive
```

### Command Line Interface

Run the server inside your project directory:

```sh
alive public/ --port 8080
```

### Programmatic Usage

Embed the server directly into your Python scripts:

```python
from alive import LiveServer

server = AliveServer("public/", port=8080)
server.run()
```

> [!tip]
> **Async Context Support**
>
> If you are already inside an existing event loop, use `await server.serve()` instead of `server.run()` to avoid blocking your application.

## 📝 License

MIT
